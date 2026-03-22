#include "util.h"

char** calculate(char* srcpath[], char* dstpath[]) {
    // Find the length of the longest common prefix
    unsigned i = 0;
    while (srcpath[i] != NULL && dstpath[i] != NULL && 
           strcmp(srcpath[i], dstpath[i]) == 0) {
        i++;
    }
    
    // Allocate path array for the common prefix
    char** compath = malloc_path(i + 1); // +1 for NULL terminator
    
    // Copy the common prefix elements
    for (unsigned j = 0; j < i; j++) {
        compath[j] = malloc_string(srcpath[j]);
    }
    
    // Set the NULL terminator
    compath[i] = NULL;
    
    return compath;
}