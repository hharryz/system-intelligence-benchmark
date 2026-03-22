#include "interface.h"

struct getattr_ret* atomfs_getattr(char* path[]) {
    struct inode* target;
    
    // Lock root_inum before calling locate
    lock(root_inum);
    
    // Traverse path starting from root_inum
    target = locate(root_inum, path);
    
    // If locate returned NULL, we have no lock owned (per locate spec)
    if (target == NULL) {
        return NULL;
    }
    
    // locate returns with target locked and all other locks released
    // Extract attributes from target inode
    unsigned mode = target->mode;
    unsigned size = target->size;
    unsigned maj = target->maj;
    unsigned min = target->min;
    
    // Allocate and populate getattr_ret structure
    struct getattr_ret* ret = malloc_getattr_ret(target, mode, size, maj, min);
    
    // Unlock the target inode before returning
    unlock(target);
    
    return ret;
}