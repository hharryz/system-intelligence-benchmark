#include "util.h"

void split_dirs_file(const char *path, char *dirname[], char *filename) {
    if (path == NULL || *path != '/' || dirname == NULL || filename == NULL) {
        return;
    }

    // Handle root path "/"
    if (path[1] == '\0') {
        return;
    }

    // Duplicate path to make it modifiable
    char *path_copy = malloc_string(path);
    if (path_copy == NULL) {
        return;
    }

    char *saveptr;
    char *token;
    int dir_index = 0;

    // Tokenize the path_copy by '/'
    token = strtok_r(path_copy, "/", &saveptr);

    // Collect all tokens (directory components and filename)
    while (token != NULL && *token != '\0') {
        if (dir_index < MAX_PATH_LEN - 1) {
            dirname[dir_index] = malloc_string(token);
            if (dirname[dir_index] == NULL) {
                break;
            }
            dir_index++;
        }
        token = strtok_r(NULL, "/", &saveptr);
    }

    // If no tokens were found, cleanup and return
    if (dir_index == 0) {
        free(path_copy);
        return;
    }

    // The last token is the filename
    // Copy it to filename buffer
    if (dirname[dir_index - 1] != NULL) {
        // Copy the string content, not the pointer
        char *last_dir = dirname[dir_index - 1];
        // Ensure we don't overflow filename buffer
        int len = 0;
        while (len < MAX_FILE_LEN - 1 && last_dir[len] != '\0') {
            filename[len] = last_dir[len];
            len++;
        }
        filename[len] = '\0';

        // Free the last directory entry and set to NULL
        free(dirname[dir_index - 1]);
        dirname[dir_index - 1] = NULL;
    }

    // Set NULL terminator after last valid directory entry
    if (dir_index > 0) {
        dirname[dir_index] = NULL;
    }

    free(path_copy);
}