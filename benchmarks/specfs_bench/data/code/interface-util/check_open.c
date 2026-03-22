#include "interface-util.h"

int check_open(struct inode *inum, unsigned mode) {
    int result;
    
    // Pre-condition: if inum is not NULL, the lock for inum is owned
    // So we need to unlock it before returning
    
    if (inum == NULL) {
        result = 1;
    } else if (inum->mode == DIR_MODE) {
        if (mode == DIR_MODE) {
            result = 0;
        } else {
            result = 1;
        }
    } else {
        if (mode == DIR_MODE) {
            result = 1;
        } else {
            result = 0;
        }
    }
    
    // Post-condition: no lock is owned, so we must unlock
    if (inum != NULL) {
        unlock(inum);
    }
    
    return result;
}