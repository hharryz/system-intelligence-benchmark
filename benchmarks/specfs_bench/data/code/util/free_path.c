#include "util.h"

void free_path(char** path) {
    if (path == NULL) {
        return;
    }
    
    char** current = path;
    while (*current != NULL) {
        free(*current);
        current++;
    }
    
    free(path);
}