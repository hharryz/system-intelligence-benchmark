#include "util.h"

char* malloc_string(const char* name) {
    size_t len = strlen(name) + 1;
    char* result = (char*)malloc(len);
    memcpy(result, name, len);
    return result;
}