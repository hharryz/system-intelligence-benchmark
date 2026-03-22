#include "interface-util.h"

int check_dir(struct inode *inum) {
    if (inum == NULL) {
        return 1;
    }
    
    if (inum->mode == DIR_MODE) {
        return 0;
    } else {
        unlock(inum);
        return 1;
    }
}