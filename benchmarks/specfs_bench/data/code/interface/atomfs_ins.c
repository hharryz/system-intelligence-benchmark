#include "interface.h"

int atomfs_ins(char* path[], char* name, int mode, unsigned maj, unsigned min) {
    // Pre-condition: no lock is owned
    lock(root_inum);
    struct inode* target = locate(root_inum, path);
    
    // If locate returns NULL, traversal failed and no lock is owned
    if (target == NULL) {
        return -1;
    }
    
    // check_ins returns 1 means no lock is owned, so we return immediately
    if (check_ins(target, name) != 0) {
        return -1;
    }
    
    // check_ins returned 0, so target is still locked
    struct inode* new_inode = malloc_inode(mode, maj, min);
    int result = inode_insert(target, new_inode, name);
    
    // Unlock target before returning to satisfy post-condition (no lock owned)
    unlock(target);
    
    // Post-condition: no lock is owned
    if (result != 0) {
        return -1;
    }
    
    return 0;
}