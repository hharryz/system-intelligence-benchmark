#include "util.h"

int getlen(char* path[]) {
    int len = 0;
    while (path[len] != NULL) {
        len++;
    }
    return len;
}