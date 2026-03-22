#include "interface-util.h"

int check_del(struct inode *cur, char *name) {
    struct inode *inum;
    
    inum = inode_find(cur, name);
    if (inum == NULL) {
        unlock(cur);
        return 1;
    }
    
    // Check if it's a non-empty directory
    if ((inum->mode & DIR_MODE) && inum->size > 0) {
        unlock(cur);
        return 1;
    }
    
    // Success case: lock for inum is acquired, cur remains locked
    lock(inum);
    return 0;
}