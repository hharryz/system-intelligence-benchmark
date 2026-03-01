"""This script runs a benchmark for evaluating patches in a software project."""

import argparse
import json
import os
import sys
from datetime import datetime

_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)
sys.path.append(os.path.abspath(os.path.join(_src_dir, '../../../')))

from sdk.logger import logger
from sdk.utils import set_llm_endpoint_from_config

set_llm_endpoint_from_config('env.toml')

from run_eval_in_env import run_eval
from utils import get_task

from agents.ae_agent.utils import (
    enable_skill_from_item,
    enable_subagent_from_item,
    gpu_from_item,
    interactive_from_item,
    resolve_project_path,
    safe_task_id,
    timeout_ms_from_item,
    write_task_report,
    compute_and_write_summary,
)


def _persist_skipped(save_path: str, task_id: str, message: str, expected_score: int = -1) -> None:
    """Append one result line for a skipped task so summary total is accurate (same as ae-agent)."""
    result = {
        'task_id': task_id,
        'status': 'skipped',
        'message': message,
        'expected_score': expected_score,
    }
    with open(os.path.join(save_path, 'result.jsonl'), 'a+', encoding='utf-8') as fw:
        fw.write(json.dumps(result, ensure_ascii=False) + '\n')


def _parse_bool(v, default=False):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in ('true', '1', 'yes')
    return bool(v) if v is not None else default


def _is_ae_agent(agent):
    """True if agent path points to the ae_agent (for report/summary writing)."""
    if not agent:
        return False
    return 'ae_agent' in agent or os.path.basename(agent) == 'ae_agent'


def main(file_path, model, agent, save_path, interactive_default=False, enable_skill_default=False, enable_subagent_default=False):
    """Main function for running the benchmark."""
    logger.info(f'Using model: {model}, agent: {agent}')
    with open(file_path) as f:
        for line in f:
            if not line.strip():
                continue  # Skip empty lines

            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                logger.info(f'Skipping invalid JSON line: {line}')
                continue

            env_val = item.get('env', None)
            if env_val is not None:
                s = str(env_val).strip().lower()
                if s == 'local':
                    run_on_host = True
                    deployment = None
                else:
                    run_on_host = False
                    deployment = str(env_val).strip() or None
            else:
                deployment = item.get('docker_env', None) or item.get('docer_env', None)
                run_on_host = item.get('run_on_host', False)
            task_id = item.get('artifact_id', None)
            project_path, path_error = resolve_project_path(item, file_path, save_path)
            if path_error:
                logger.info(f"Task {task_id}: {path_error}")
                _persist_skipped(
                    save_path,
                    task_id or safe_task_id(task_id),
                    path_error,
                    item.get('expected_score', -1),
                )
                continue
            task_file = item.get('artifact_readme', None)
            test_method = item.get('evaluator', None)

            timeout_ms = timeout_ms_from_item(item)
            gpu = gpu_from_item(item)
            interactive = interactive_from_item(item) or interactive_default
            enable_skill = enable_skill_from_item(item, enable_skill_default)
            enable_subagent = enable_subagent_from_item(item, enable_subagent_default)
            keep_container = _parse_bool(item.get('keep_container'), False)

            task = get_task(task_file)

            logger.info(
                f"Task {task_id}: project_path={project_path}, run_on_host={run_on_host}, "
                f"timeout_ms={timeout_ms}, gpu={gpu}, interactive={interactive}, "
                f"enable_skill={enable_skill}, enable_subagent={enable_subagent}, keep_container={keep_container}"
            )

            result = run_eval(
                deployment=deployment,
                project_path=project_path,
                task_id=task_id,
                task=task,
                model=model,
                agent_path=agent,
                test_method=test_method,
                save_path=save_path,
                run_on_host=run_on_host,
                timeout_ms=timeout_ms,
                gpu=gpu,
                interactive=interactive,
                enable_skill=enable_skill,
                enable_subagent=enable_subagent,
                keep_container=keep_container,
            )

            result['expected_score'] = item.get('expected_score', -1)
            result['timestamp'] = result.get('timestamp') or datetime.now().isoformat()
            with open(f'{save_path}/result.jsonl', 'a+', encoding='utf-8') as fw:
                fw.write(json.dumps(result, ensure_ascii=False) + '\n')

            # When using ae_agent, also write per-task AE report (same as standalone ae-agent).
            if _is_ae_agent(agent):
                safe_id = safe_task_id(task_id)
                log_path = result.get('log_file') or '(log not captured when run via benchmark)'
                agent_summary = (result.get('agent_run_results') or '')[:8000] or '(No summary captured)'
                try:
                    write_task_report(save_path, safe_id, task_id, result, log_path, agent_summary)
                except Exception as e:
                    logger.warning('write_task_report failed: %s', e)

    # Write summary.json (total/success counts) when ae_agent was used.
    if _is_ae_agent(agent):
        try:
            compute_and_write_summary(save_path)
        except Exception as e:
            logger.warning('compute_and_write_summary failed: %s', e)

    success_count = 0
    total_count = 0
    with open(f'{save_path}/result.jsonl', encoding='utf-8') as f:
        for line in f:
            result = json.loads(line.strip())
            if result.get('status') == 'success':
                success_count += (result.get('score') == result.get('expected_score', -1))
            total_count += 1
    logger.info(f'Test run completed: {success_count}/{total_count} tasks succeeded.')
    summary_data = {'final_score': success_count / total_count, 'total_tasks': total_count}

    with open(os.path.join(save_path, 'avg_score.json'), 'w', encoding='utf-8') as summary_file:
        json.dump(summary_data, summary_file, indent=4)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='example benchmark')
    parser.add_argument(
        '-i',
        '--input_file',
        help='Benchmark input file',
        default='./data/benchmark/arteval_tasks.jsonl',
        #default='./data/benchmark/env_setup_examples.jsonl',
    )
    parser.add_argument('-o', '--save_path', help='Result save path', default=None)
    parser.add_argument(
        '-a',
        '--agent',
        help='Agent Name',
        default='claudecode',
    )
    parser.add_argument(
        '-m',
        '--model_name',
        help='Model Name',
        default='claude-sonnet-4-5-20250929',
    )
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Enable interactive mode (continue giving agent instructions after task completes)',
    )
    parser.add_argument(
        '--enable-skill',
        action='store_true',
        help='Enable Claude Agent SDK Skill (load from ~/.claude/skills/)',
    )
    parser.add_argument(
        '--enable-subagent',
        action='store_true',
        help='Enable Claude Agent SDK Sub-agent (Task tool)',
    )
    # Note that if your benchmark has multiple tasks, you need to add --task <task>
    # in your code to enable task selection.
    parser.add_argument('-t', '--task', help='specify task in scenarios', default=None)

    args = parser.parse_args()

    model_name = args.model_name
    agent = args.agent
    input_file = args.input_file
    save_path = args.save_path
    task = args.task

    logger.debug(f"Benchmark path: {input_file}")

    if save_path is None:
        str_model_name = model_name.replace('/', '_')
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        save_path = os.path.join('./outputs', f'env_setup_project__{str_model_name}__{args.agent}__{timestamp}')

    _src_dir = os.path.dirname(os.path.abspath(__file__))
    if agent == 'claudecode':
        agent = os.path.join(_src_dir, 'agents', 'claudecode')
    elif agent == 'claude_sdk':
        agent = os.path.join(_src_dir, 'agents', 'claude_sdk')
    elif agent == 'ae_agent' or agent == 'ae-agent':
        agent = os.path.join(_src_dir, 'agents', 'ae_agent')
    save_path = os.path.abspath(os.path.expanduser(save_path))
    os.makedirs(save_path, exist_ok=True)

    main(
        input_file,
        model_name,
        agent,
        save_path,
        interactive_default=getattr(args, 'interactive', False),
        enable_skill_default=getattr(args, 'enable_skill', False),
        enable_subagent_default=getattr(args, 'enable_subagent', False),
    )
