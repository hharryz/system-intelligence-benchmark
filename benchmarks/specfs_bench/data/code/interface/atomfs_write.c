#include "interface.h"

int atomfs_write(char* path[], const char* buf, unsigned size, unsigned offset) {
    struct inode* inum = locate(root_inum, path);
    
    if (inum == NULL) {
        return -1;
    }
    
    if (check_file(inum) == 1) {
        return -1;
    }
    
    unsigned result = inode_write(inum, buf, size, offset);
    unlock(inum);
    return (int)result;
}