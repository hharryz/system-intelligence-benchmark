#include "util.h"

char** malloc_path(unsigned len) {
    char** paths = (char**)malloc(len * sizeof(char*));
    for (unsigned i = 0; i < len; i++) {
        paths[i] = NULL;
    }
    return paths;
}