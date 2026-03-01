"""Patch evaluator for running tests in a deployment."""

import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../')))

from swerex.deployment.docker import DockerDeploymentConfig
from swerex.runtime.abstract import BashAction, Command, CreateBashSessionRequest, UploadRequest

from sdk.logger import logger


def _parse_eval_score(output) -> int:
    """Parse evaluation score from BashObservation or string output.

    - If a line is a single digit (e.g. '4', '0'), use it (prefer last such line).
    - If output contains 'Agent scores: {...}' (Oracle-style evaluator), count ': 1' as passed items.
    - Otherwise return 0.
    """
    s = (getattr(output, "output", None) or str(output) or "").strip()
    if not s:
        return 0
    lines = s.splitlines()
    for line in reversed(lines):
        t = line.strip()
        if t.isdigit():
            return int(t)
    m = re.search(r"Agent scores:\s*\{[^}]*\}", s)
    if m:
        return m.group(0).count(": 1")
    return 0


def write_to_file(file_path, content):
    """Write content to a file."""
    with open(file_path, 'w') as f:
        f.write(content)


def setup_claude_settings_on_host():
    """Set up ~/.claude/settings.json with timeout configuration on host."""
    claude_dir = Path.home() / ".claude"
    settings_file = claude_dir / "settings.json"
    
    claude_dir.mkdir(exist_ok=True)
    
    settings = {
        "env": {
            "BASH_MAX_TIMEOUT_MS": "345600000",  # 96 hours
            "BASH_DEFAULT_TIMEOUT_MS": "345600000"
        }
    }
    
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=2)
    
    logger.info(f"Created {settings_file} with 96-hour timeout configuration.")


def _is_ae_agent_path(agent_path) -> bool:
    """True if agent_path points to the ae_agent agent (same flow: agent + evaluation script)."""
    if not agent_path:
        return False
    p = (agent_path or "").rstrip(os.sep)
    return p.endswith("ae_agent") or os.path.basename(p) == "ae_agent"


def _stdin_is_tty() -> bool:
    """True if stdin is a TTY (required for docker exec -it)."""
    return getattr(sys.stdin, "isatty", lambda: False)()


async def _get_container_id_from_runtime(runtime, deployment) -> str:
    """Get Docker container ID from inside the container (hostname/cgroup) or from deployment."""
    container_id = "unknown"
    try:
        res = await runtime.run_in_session(
            BashAction(command='cat /etc/hostname 2>/dev/null || hostname 2>/dev/null || echo "unknown"', timeout=10.0)
        )
        container_id = str(getattr(res, "output", "")).strip()
        try:
            cgroup_res = await runtime.run_in_session(
                BashAction(command='cat /proc/self/cgroup 2>/dev/null | grep docker | head -1 | cut -d/ -f3 | cut -c1-12 || echo ""', timeout=10.0)
            )
            cid = str(getattr(cgroup_res, "output", "")).strip()
            if cid:
                container_id = cid
        except Exception:
            pass
        if hasattr(deployment, '_container_id') and getattr(deployment, '_container_id', None):
            container_id = deployment._container_id
        elif hasattr(deployment, 'container_id') and getattr(deployment, 'container_id', None):
            container_id = deployment.container_id
    except Exception as e:
        logger.warning('Failed to get container ID: %s', e)
    return container_id


async def _run_ae_agent_interactive_foreground(
    container_id: str,
    model: str,
    timeout_ms: int | None,
    enable_skill: bool,
    enable_subagent: bool,
):
    """Run ae_agent runner in foreground via docker exec -it (interactive mode). Returns MockResult with exit_code."""
    try:
        from agents.ae_agent.utils import resolve_timeout_ms
        from agents.ae_agent.run_eval import _docker_exec_env_args
    except ImportError:
        _src = os.path.dirname(os.path.abspath(__file__))
        if _src not in sys.path:
            sys.path.insert(0, _src)
        from agents.ae_agent.utils import resolve_timeout_ms
        from agents.ae_agent.run_eval import _docker_exec_env_args

    timeout_resolved = resolve_timeout_ms(timeout_ms)
    exec_env = _docker_exec_env_args(
        timeout_resolved,
        enable_skill=enable_skill,
        enable_subagent=enable_subagent,
    )
    exec_args = (
        ['docker', 'exec', '-it']
        + exec_env
        + [container_id, 'python3', '-u', '/agent/runner.py', model, '/agent/current_task.txt', '--interactive']
    )
    logger.info('Running ae_agent in interactive mode (foreground): docker exec -it %s ...', container_id[:12])
    proc = await asyncio.to_thread(
        subprocess.run,
        exec_args,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    exit_code = proc.returncode if proc else -1

    class MockResult:
        def __init__(self, code, output=''):
            self.exit_code = code
            self.output = output or f'exit_code={code}'

    return MockResult(exit_code, f'Interactive session (exit_code={exit_code})')


async def run_eval_on_host(
    project_path,
    task_id,
    task,
    model,
    agent_path,
    test_method,
    save_path,
    timeout_ms=None,
    interactive=False,
    enable_skill=False,
    enable_subagent=False,
):
    """Run evaluation directly on host machine (no Docker container).

    When agent is ae_agent, delegates to ae_agent.run_agent_then_eval (agent run + evaluation script),
    same flow as claude_sdk. Otherwise uses inline Claude SDK + test_method.
    """
    logger.info("=" * 80)
    logger.info("Running evaluation directly on HOST MACHINE (not in Docker)")
    logger.info("=" * 80)

    if _is_ae_agent_path(agent_path):
        logger.info("Using ae_agent flow: run agent then evaluation script.")
        try:
            from agents.ae_agent.run_eval import _run_agent_then_eval_async
        except ImportError:
            _src = os.path.dirname(os.path.abspath(__file__))
            if _src not in sys.path:
                sys.path.insert(0, _src)
            from agents.ae_agent.run_eval import _run_agent_then_eval_async
        result = await _run_agent_then_eval_async(
            project_path=project_path,
            task_id=task_id,
            task=task,
            model=model,
            test_method=test_method,
            save_path=save_path,
            timeout_ms=timeout_ms,
            skip_prereq_check=False,
            interactive=interactive,
            enable_skill=enable_skill,
            enable_subagent=enable_subagent,
        )
        return result

    # Original flow: inline Claude SDK then test_method (e.g. claude_sdk or default)
    import shutil

    if not shutil.which("docker"):
        raise RuntimeError("Docker is not installed on host")

    result = subprocess.run(["docker", "ps"], capture_output=True, timeout=10)
    if result.returncode != 0:
        raise RuntimeError("Docker is not running on host")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")

    setup_claude_settings_on_host()

    project_path = os.path.abspath(project_path)
    if not os.path.isdir(project_path):
        raise RuntimeError(f"Project path does not exist: {project_path}")

    logger.info(f"Project path: {project_path}")
    logger.info(f"Task ID: {task_id}")
    logger.info(f"Model: {model}")

    try:
        from claude_agent_sdk import query, ClaudeAgentOptions
    except ImportError as e:
        raise RuntimeError(f"claude_agent_sdk not installed: {e}. Install with: pip install claude-agent-sdk")

    system_prompt = f"""You are an experienced software engineer completing an artifact evaluation task.

ENVIRONMENT SETUP (HOST MACHINE - NOT DOCKER):
- You are running DIRECTLY on the host machine (NOT inside a Docker container)
- Docker daemon is already running on this host
- When you use Kind to create Kubernetes clusters, they will be created using the host's Docker
- This avoids Docker-in-Docker compatibility issues
- You may need sudo for some operations

ARTIFACT LOCATION:
- The artifact repository is located at: {project_path}
- Start by changing to this directory: cd {project_path}

YOUR TASK:
{task}

TIMEOUT CONFIGURATION (CRITICAL):
- Long-running commands (builds, tests, Kind cluster creation) are expected
- DO NOT set short timeouts - let commands complete naturally
- Kind cluster creation can take 5-10 minutes
- Full benchmark runs can take hours

IMPORTANT GUIDELINES:
1. First, cd to {project_path} and examine the directory structure
2. Follow the README instructions step by step
3. If you see 'sudo' in instructions, you can use it (or skip if already root)
4. Use the Bash tool to run commands, Read tool to inspect files
5. Work systematically through setup, build, and experiment execution
6. If you encounter errors, debug and resolve them using available tools
7. For Kind clusters, they will work properly since you're on the host (not DinD)"""

    options = ClaudeAgentOptions(
        system_prompt=system_prompt,
        allowed_tools=["Read", "Write", "Bash"],
        setting_sources=["user"],
    )

    os.environ['BASH_MAX_TIMEOUT_MS'] = '345600000'
    os.environ['BASH_DEFAULT_TIMEOUT_MS'] = '345600000'

    logger.info("Starting Claude Agent SDK (Host Mode)...")

    message_count = 0
    run_results_output = ""

    try:
        async for message in query(
            prompt=f"Please start the artifact evaluation task. Begin by changing to the artifact directory at {project_path} and examining its contents.",
            options=options
        ):
            message_count += 1
            if message_count % 10 == 0:
                logger.info(f"[Progress] Processed {message_count} messages...")
            msg_str = str(message)
            logger.info(msg_str)
            if 'ResultMessage' in msg_str or 'TextBlock' in msg_str:
                run_results_output = msg_str
        logger.info(f"Claude Agent SDK execution completed. Total messages: {message_count}")
    except Exception as e:
        logger.error(f"Claude Agent SDK execution failed: {e}")
        import traceback
        traceback.print_exc()
        run_results_output = f"Error: {e}"

    logger.info("Running evaluation script...")
    try:
        eval_cmd = f"cd {project_path} && {test_method}"
        eval_result = subprocess.run(
            eval_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300
        )
        test_output = eval_result.stdout.strip()
        logger.info(f"Evaluation output: {test_output}")
        result = {
            'task_id': task_id,
            'task': task,
            'project_path': project_path,
            'agent_run_results': run_results_output,
            'test_method': test_method,
            'score': _parse_eval_score(test_output),
            'status': 'success',
            'run_on_host': True,
        }
    except Exception as e:
        logger.error(f"Error running test method: {e}")
        result = {
            'task_id': task_id,
            'task': task,
            'project_path': project_path,
            'agent_run_results': run_results_output,
            'test_method': test_method,
            'score': 0,
            'status': f'error: {str(e)}',
            'run_on_host': True,
        }

    return result


async def run_eval_in_env(
    deployment,
    project_path,
    task_id,
    task,
    model,
    agent_path,
    test_method,
    save_path,
    timeout_ms=None,
    gpu=False,
    interactive=False,
    enable_skill=False,
    enable_subagent=False,
    keep_container=True,
):
    """Spoiler: This function will work with any deployment."""
    await deployment.start()
    runtime = deployment.runtime

    # Default 96h when timeout_ms not provided
    runner_timeout_sec = (timeout_ms / 1000.0) if timeout_ms is not None else 345600.0
    if hasattr(runtime, "_config"):
        logger.info(f"Current RemoteRuntime timeout: {runtime._config.timeout}s")
        runtime._config.timeout = runner_timeout_sec
        logger.info(f"Overriding RemoteRuntime timeout to {runtime._config.timeout}s")

    # Issue a few one-off commands, similar to `subprocess.run()`
    logger.info(await runtime.execute(Command(command=['echo', 'Hello, world!'])))

    # Create a bash session
    await runtime.create_session(CreateBashSessionRequest())
    # Run a command in the session
    # The difference to the one-off commands is that environment state persists!
    logger.info(await runtime.run_in_session(BashAction(command="export MYVAR='test'")))
    logger.info(await runtime.run_in_session(BashAction(command='echo $MYVAR')))

    logger.info('Uploading project files...')
    logger.info(
        await runtime.upload(
            UploadRequest(
                source_path=project_path,
                target_path='/repo',
            )
        )
    )
    logger.info('Project files uploaded.')
    
    # Long-running agents (claude_sdk, ae_agent): remove eval script dirs so the agent cannot see evaluation logic
    is_claude_sdk = str(agent_path).endswith('claude_sdk')
    is_ae_agent = str(agent_path).endswith('ae_agent')
    is_long_running_agent = is_claude_sdk or is_ae_agent
    agent_label = 'ae_agent' if is_ae_agent else 'claude_sdk'
    if is_long_running_agent:
        logger.info(f'Removing _agent_eval directories for {agent_label} to prevent answer leakage...')
        await runtime.run_in_session(
            BashAction(command='find /repo -type d -name "_agent_eval" -exec rm -rf {} + 2>/dev/null || true', timeout=30.0)
        )
        logger.info('_agent_eval directories removed.')
    
    run_results = await runtime.run_in_session(BashAction(command='cd /repo'))
    logger.info(run_results)
    run_results = await runtime.run_in_session(BashAction(command='pwd'))
    logger.info(f'Current directory: {run_results}')
    run_results = await runtime.run_in_session(BashAction(command='ls'))
    logger.info(f'Current directory contents: {run_results}')

    logger.info('Uploading agent runner script...')
    logger.info(
        await runtime.upload(
            UploadRequest(
                source_path=agent_path,
                target_path='/agent',
            )
        )
    )
    logger.info(await runtime.run_in_session(BashAction(command='ls /agent/runner.sh')))
    logger.info('Agent runner script uploaded.')

    logger.info('Setup the agent running environment...')
    logger.info(await runtime.run_in_session(BashAction(command='chmod +x /agent/runner.sh /agent/install.sh')))
    logger.info(await runtime.run_in_session(BashAction(command='cat /agent/runner.sh')))
    logger.info(await runtime.run_in_session(BashAction(command='/agent/install.sh')))
    
    # Set required env vars for long-running agents (passed from host into container)
    if is_long_running_agent:
        parts = []
        anthropic_api_key = os.environ.get('ANTHROPIC_API_KEY')
        foundry_api_key = os.environ.get('ANTHROPIC_FOUNDRY_API_KEY')
        if anthropic_api_key:
            escaped_key = anthropic_api_key.replace("'", "'\"'\"'")
            parts.append(f"export ANTHROPIC_API_KEY='{escaped_key}'")
        if foundry_api_key:
            escaped_foundry = foundry_api_key.replace("'", "'\"'\"'")
            parts.append(f"export ANTHROPIC_FOUNDRY_API_KEY='{escaped_foundry}'")
            if not anthropic_api_key:
                parts.append(f"export ANTHROPIC_API_KEY='{escaped_foundry}'")
        foundry_base = os.environ.get('ANTHROPIC_FOUNDRY_BASE_URL')
        if foundry_base:
            escaped_url = foundry_base.replace("'", "'\"'\"'")
            parts.append(f"export ANTHROPIC_FOUNDRY_BASE_URL='{escaped_url}'")
        if os.environ.get('CLAUDE_CODE_USE_FOUNDRY') == '1':
            parts.append("export CLAUDE_CODE_USE_FOUNDRY=1")
        if enable_skill:
            parts.append("export AE_ENABLE_SKILL=1")
        if enable_subagent:
            parts.append("export AE_ENABLE_SUBAGENT=1")
        if parts:
            set_env_cmd = " && ".join(parts)
            logger.info('Setting Anthropic/Foundry API key and env in container...')
            logger.info(await runtime.run_in_session(BashAction(command=set_env_cmd)))
        if not anthropic_api_key and not foundry_api_key:
            logger.warning('Neither ANTHROPIC_API_KEY nor ANTHROPIC_FOUNDRY_API_KEY found. Runner may fail.')

    # For ae_agent: upload task to /agent/current_task.txt to avoid shell quoting with large tasks
    if is_ae_agent:
        tmpdir = tempfile.mkdtemp(prefix='ae_agent_task_')
        try:
            task_file_host = os.path.join(tmpdir, 'current_task.txt')
            with open(task_file_host, 'w', encoding='utf-8') as f:
                f.write(task)
            await runtime.upload(UploadRequest(source_path=tmpdir, target_path='/agent_task_file'))
            await runtime.run_in_session(BashAction(command='cp /agent_task_file/current_task.txt /agent/current_task.txt', timeout=10.0))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
        logger.info('Task file uploaded to /agent/current_task.txt for ae_agent.')

    logger.info('Running runner script...')
    if timeout_ms is not None:
        runner_timeout = timeout_ms / 1000.0
    else:
        runner_timeout = 345600.0 if is_long_running_agent else 1200.0  # 96h for long-running agents

    run_results = None
    # Docker + interactive: run ae_agent in foreground via docker exec -it (same as standalone ae-agent).
    if is_ae_agent and interactive and _stdin_is_tty():
        container_id_early = await _get_container_id_from_runtime(runtime, deployment)
        if container_id_early and container_id_early != "unknown":
            try:
                run_results = await _run_ae_agent_interactive_foreground(
                    container_id_early, model, timeout_ms, enable_skill, enable_subagent
                )
                logger.info('ae_agent interactive session finished with exit_code=%s', run_results.exit_code)
            except Exception as e:
                logger.warning('ae_agent interactive foreground failed: %s', e)
        else:
            logger.warning('Cannot get container ID for interactive mode; falling back to non-interactive.')

    if run_results is None:
        if is_long_running_agent:
            # Live log monitoring: run runner in background, poll log file periodically
            await runtime.run_in_session(BashAction(command='rm -f /agent/runner.live.log && touch /agent/runner.live.log', timeout=10.0))

            # ae_agent: use task file to avoid shell quoting; others pass task string
            if is_ae_agent:
                start_cmd = (
                    'stdbuf -oL -eL /agent/runner.sh "' + model + '" /agent/current_task.txt > /agent/runner.live.log 2>&1 & '
                    'RUNNER_PID=$!; '
                    'sleep 1; '
                    'echo RUNNER_PID=$RUNNER_PID'
                )
            else:
                start_cmd = (
                    f'bash -c "stdbuf -oL -eL /agent/runner.sh \\"{model}\\" \\"{task}\\" > /agent/runner.live.log 2>&1 & '
                    'RUNNER_PID=$!; '
                    'sleep 1; '
                    'echo RUNNER_PID=$RUNNER_PID"'
                )
            start_res = await runtime.run_in_session(BashAction(command=start_cmd, timeout=30.0))
            start_output = str(getattr(start_res, "output", "")).strip()

            pid = None
            for line in start_output.split('\n'):
                if 'RUNNER_PID=' in line:
                    pid = line.split('RUNNER_PID=', 1)[1].strip()
                    break

            if not pid or not pid.isdigit():
                # Fallback: find PID by process name after short delay
                await asyncio.sleep(2)
                ps_res = await runtime.run_in_session(
                    BashAction(command="ps aux | grep '[r]unner.py' | awk '{print $2}' | head -1", timeout=10.0)
                )
                pid = str(getattr(ps_res, "output", "")).strip()

            logger.info(f'{agent_label} runner started with pid: {pid}')

            await asyncio.sleep(2)  # Allow log file to have content

            elapsed = 0.0
            poll_interval = 10.0  # Poll every 10s for live log
            run_results = None
            last_log_content = ""  # Track last read content to avoid duplicate output

            while elapsed < runner_timeout:
                try:
                    log_res = await runtime.run_in_session(
                        BashAction(command='cat /agent/runner.live.log 2>/dev/null || echo ""', timeout=30.0)
                    )
                    current_log_content = str(getattr(log_res, "output", "")).strip()

                    if current_log_content and current_log_content != last_log_content:
                        if last_log_content and current_log_content.startswith(last_log_content):
                            new_content = current_log_content[len(last_log_content):].strip()
                            if new_content:
                                logger.info(f'[{agent_label} live log @ {elapsed:.0f}s ({elapsed/60:.1f} min)]\n{new_content}')
                        else:
                            logger.info(f'[{agent_label} live log @ {elapsed:.0f}s ({elapsed/60:.1f} min)]\n{current_log_content}')
                        last_log_content = current_log_content
                    elif elapsed % 300 == 0 and elapsed > 0:
                        logger.info(f'[{agent_label} still running @ {elapsed:.0f}s ({elapsed/60:.1f} min), no new output]')
                except Exception as e:
                    logger.info(f'Failed to read {agent_label} live log: {e}')

                if pid and pid.isdigit():
                    ps_res = await runtime.run_in_session(
                        BashAction(command=f'ps -p {pid} >/dev/null 2>&1; echo $?', timeout=10.0)
                    )
                    ps_code = str(getattr(ps_res, "output", "")).strip()
                    if ps_code != "0":
                        wait_res = await runtime.run_in_session(
                            BashAction(command=f'wait {pid} 2>/dev/null; echo $?', timeout=30.0)
                        )
                        exit_code_str = str(getattr(wait_res, "output", "")).strip()

                        class MockResult:
                            def __init__(self, code):
                                self.exit_code = int(code) if code.isdigit() else 0
                                self.output = f'exit_code={self.exit_code}'
                        run_results = MockResult(exit_code_str)
                        logger.info(f'{agent_label} runner finished with exit code: {run_results.exit_code}')
                        break
                else:
                    ps_res = await runtime.run_in_session(
                        BashAction(command="ps aux | grep '[r]unner.py' | wc -l", timeout=10.0)
                    )
                    proc_count = str(getattr(ps_res, "output", "")).strip()
                    if proc_count == "0" or not proc_count.isdigit() or int(proc_count) == 0:
                        logger.info(f'{agent_label} runner process not found, assuming finished')
                        class MockResult:
                            def __init__(self):
                                self.exit_code = 0
                                self.output = 'exit_code=0'
                        run_results = MockResult()
                        break

                await asyncio.sleep(poll_interval)
                elapsed += poll_interval

            if run_results is None:
                # Timeout: try to kill process and capture final log
                if pid and pid.isdigit():
                    try:
                        await runtime.run_in_session(BashAction(command=f'kill -TERM {pid} 2>/dev/null || kill -9 {pid} 2>/dev/null || true', timeout=10.0))
                    except Exception:
                        pass
                try:
                    tail_log = await runtime.run_in_session(
                        BashAction(command='tail -n 200 /agent/runner.live.log', timeout=30.0)
                    )
                    logger.info(f'{agent_label} live log tail (on timeout):\n{tail_log}')
                except Exception as e:
                    logger.info(f'Failed to read {agent_label} live log after timeout: {e}')
                raise TimeoutError(f'{agent_label} runner exceeded timeout {runner_timeout}s')

        else:
            runner_cmd = f'/agent/runner.sh "{model}" "{task}"'
            run_results = await runtime.run_in_session(BashAction(command=runner_cmd, timeout=runner_timeout))
    logger.info(f"agent's run results: {run_results}")
    logger.info('Runner script finished.')

    # For long-running agents: upload eval scripts before running evaluation
    if is_long_running_agent:
        logger.info(f'Uploading _agent_eval directories for evaluation ({agent_label})...')
        eval_dirs = []
        for root, dirs, files in os.walk(project_path):
            if '_agent_eval' in dirs:
                eval_source_path = os.path.join(root, '_agent_eval')
                rel_path = os.path.relpath(eval_source_path, project_path)
                eval_dirs.append((eval_source_path, rel_path))

        if eval_dirs:
            for eval_source_path, rel_path in eval_dirs:
                target_eval_path = os.path.join('/repo', rel_path)
                logger.info(f'Uploading _agent_eval from {eval_source_path} to {target_eval_path}')
                try:
                    await runtime.upload(
                        UploadRequest(
                            source_path=eval_source_path,
                            target_path=target_eval_path,
                        )
                    )
                    logger.info(f'_agent_eval directory uploaded: {rel_path}')
                except Exception as e:
                    logger.warning(f'Failed to upload _agent_eval from {eval_source_path}: {e}')
            logger.info('All _agent_eval directories uploaded for evaluation.')
        else:
            logger.warning(f'No _agent_eval directories found in {project_path}')

    try:
        test_output = await runtime.run_in_session(BashAction(command=test_method))
        logger.info(test_output)
        result = {
            'task': task,
            'project_path': project_path,
            'agent_run_results': run_results.output if hasattr(run_results, 'output') else str(run_results),
            'test_method': test_method,
            'score': _parse_eval_score(test_output),
            'status': 'success',
        }
    except Exception as e:
        logger.info(f'Error running test method: {e}')
        result = {
            'task': task,
            'project_path': project_path,
            'agent_run_results': run_results.output if hasattr(run_results, 'output') else str(run_results),
            'test_method': test_method,
            'score': 0,
            'status': f'error: {str(e)}',
        }

    # For long-running agents: sync+stop (when keep_container=False) or keep container for inspection
    if is_long_running_agent:
        container_id = await _get_container_id_from_runtime(runtime, deployment)
        container_name = (
            getattr(deployment, '_container_name', None)
            or getattr(deployment, 'container_name', None)
            or 'unknown'
        )

        if is_ae_agent and not keep_container and container_id and container_id != "unknown":
            # Original artifact-agent behavior: sync workspace, commit image, stop container
            try:
                from agents.ae_agent.run_eval import save_container_after_run
                saved_image, container_stopped = save_container_after_run(container_id, project_path, task_id)
                result['saved_image'] = saved_image
                result['container_stopped'] = container_stopped
                result['container_id'] = container_id
                result['container_kept'] = False
                logger.info(f'ae_agent: synced workspace, saved image={saved_image}, stopped={container_stopped}')
            except Exception as e:
                logger.warning(f'save_container_after_run failed: {e}')
                result['container_id'] = container_id
                result['container_kept'] = True
            try:
                await deployment.stop()
            except Exception as e:
                logger.warning(f'deployment.stop() failed: {e}')
        elif keep_container:
            logger.info('=' * 80)
            logger.info(f'Keeping Docker container running for {agent_label} (for debugging purposes).')
            logger.info(f'Container ID: {container_id}')
            logger.info(f'Task ID: {task_id}')
            logger.info(f'Project Path: {project_path}')
            logger.info(f'  To inspect: docker exec -it {container_id} /bin/bash')
            logger.info(f'  To stop: docker stop {container_id}')
            logger.info('=' * 80)
            result['container_id'] = container_id
            result['container_name'] = container_name
            result['container_kept'] = True
        else:
            await deployment.stop()
            result['container_id'] = container_id
            result['container_kept'] = False
    else:
        await deployment.stop()
        result['container_kept'] = False

    
    return result


def run_eval(
    deployment,
    project_path,
    task_id,
    task,
    model,
    agent_path,
    test_method,
    save_path,
    run_on_host=False,
    timeout_ms=None,
    gpu=False,
    interactive=False,
    enable_skill=False,
    enable_subagent=False,
    keep_container=True,
):
    """Run evaluation either on host or in Docker container.

    Args:
        deployment: Docker image to use (ignored if run_on_host=True)
        project_path: Path to the artifact project
        task_id: Task identifier
        task: Task description
        model: Model name
        agent_path: Path to agent scripts
        test_method: Evaluation command
        save_path: Path to save results
        run_on_host: If True, run directly on host machine instead of Docker
        timeout_ms: Per-task timeout in milliseconds (None = default 96h for long-running agents)
        gpu: If True, pass --gpus all to Docker (Docker mode only)
        interactive: If True, enable interactive mode after task (ae_agent only)
        enable_skill: If True, enable Claude Agent SDK Skill (ae_agent only)
        enable_subagent: If True, enable Claude Agent SDK Sub-agent (ae_agent only)
        keep_container: If False and ae_agent, sync workspace + commit image + stop container after run
    """

    if run_on_host:
        logger.info(f"Task {task_id} configured to run on HOST machine (run_on_host=True)")
        return asyncio.run(
            run_eval_on_host(
                project_path,
                task_id,
                task,
                model,
                agent_path,
                test_method,
                save_path,
                timeout_ms=timeout_ms,
                interactive=interactive,
                enable_skill=enable_skill,
                enable_subagent=enable_subagent,
            )
        )

    # Run in Docker container
    image = deployment or 'bastoica/ae-agent-ubuntu24.04:latest'

    docker_args = [
        '--privileged',
        '--cgroupns=host',
        '-e', 'KIND_EXPERIMENTAL_CONTAINERD_SNAPSHOTTER=native',
    ]
    if gpu:
        docker_args.extend(['--gpus', 'all'])

    config = DockerDeploymentConfig(
        image=image,
        startup_timeout=1200.0,
        docker_args=docker_args,
    )
    deployment_obj = config.get_deployment()

    return asyncio.run(
        run_eval_in_env(
            deployment_obj,
            project_path,
            task_id,
            task,
            model,
            agent_path,
            test_method,
            save_path,
            timeout_ms=timeout_ms,
            gpu=gpu,
            interactive=interactive,
            enable_skill=enable_skill,
            enable_subagent=enable_subagent,
            keep_container=keep_container,
        )
    )



def test():
    task = 'The java is not installed. Can you please setup it? Note: you are in a docker with root permission. DO NOT use sudo.'
    project_path = '../data/benchmark/projects/test-repo'
    test_method = 'java -version'
    deployment = 'xuafeng/swe-go-python:latest'
    model = 'claude-sonnet-4-5-20250929'
    agent_path = './agents/claudecode'
    save_path = './eval_results'
    task_id = 'test_task_1'
    result = run_eval(deployment, project_path, task_id, task, model, agent_path, test_method, save_path)
    print('Test result:', result)


# TODO: still work on add openhand agent
def test1():
    task = 'The java is not installed. Can you please setup it? Note: you are in a docker with root permission. DO NOT use sudo.'
    project_path = '../data/benchmark/projects/test-repo'
    test_method = 'java -version'
    deployment = 'xuafeng/swe-go-python:latest'
    model = 'claude-sonnet-4-5-20250929'
    agent_path = './agents/openhand'
    save_path = './eval_results'
    task_id = 'test_task_1'
    result = run_eval(deployment, project_path, task_id, task, model, agent_path, test_method, save_path)
    print('Test result:', result)


def test2():
    task = "create a python file named hello.py that prints 'hello world'"
    project_path = '../data/benchmark/projects/test-repo'
    test_method = 'python hello.py'
    deployment = 'xuafeng/swe-go-python:latest'
    model = 'claude-sonnet-4-5-20250929'
    agent_path = './agents/claudecode'
    save_path = './eval_results'
    task_id = 'test_task_1'
    eval_out = asyncio.run(
        run_eval_in_env(deployment, project_path, task_id, task, model, agent_path, test_method, save_path)
    )
    print(eval_out)


if __name__ == '__main__':
    test1()
