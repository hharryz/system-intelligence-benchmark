#include "util.h"

void split_dirs(const char *path, char *dirname[]) {
    char *temp_path = malloc_string(path);
    char *saveptr;
    char *token;
    int i = 0;

    token = strtok_r(temp_path, "/", &saveptr);
    while (token != NULL) {
        // Assert number of tokens does not exceed MAX_PATH_LEN
        if (i >= MAX_PATH_LEN) {
            break;
        }
        // Assert token length does not exceed MAX_FILE_LEN
        if (strlen(token) > MAX_FILE_LEN) {
            break;
        }
        dirname[i] = malloc_string(token);
        i++;
        token = strtok_r(NULL, "/", &saveptr);
    }

    // Null-terminate the dirname array if needed (though spec doesn't require it)
    // The spec only requires populating with allocated strings for each component

    free(temp_path);
}