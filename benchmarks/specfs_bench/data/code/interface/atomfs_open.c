#include "interface.h"

struct inode *atomfs_open(char *path[], unsigned mode) {
    struct inode *inum;
    
    lock(root_inum);
    inum = locate(root_inum, path);
    
    if (inum == NULL) {
        return NULL;
    }
    
    if (check_open(inum, mode) != 0) {
        return NULL;
    }
    
    return inum;
}