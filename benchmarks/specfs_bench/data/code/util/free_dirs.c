#include "util.h"

void free_dirs(char *dirname[]) {
    for (int i = 0; dirname[i] != NULL; i++) {
        free(dirname[i]);
    }
}