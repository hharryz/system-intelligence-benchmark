#include "util.h"

unsigned int hash_name(char* name) {
    unsigned int hash = 0;
    
    if (name == NULL || *name == '\0') {
        return 0;
    }
    
    for (int i = 0; name[i] != '\0'; i++) {
        hash = (hash * 131) + (unsigned char)name[i];
    }
    
    return hash & 0x1ff;
}