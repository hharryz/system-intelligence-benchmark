#include "util.h"

struct getattr_ret* malloc_getattr_ret(struct inode* inum, unsigned mode, unsigned size, unsigned maj, unsigned min) {
    struct getattr_ret* ret = (struct getattr_ret*)malloc(sizeof(struct getattr_ret));
    if (ret == NULL) {
        return NULL;
    }
    
    ret->inum = inum;
    ret->mode = mode;
    ret->size = size;
    
    // Directories should have device numbers set to 0
    if (mode == DIR_MODE) {
        ret->maj = 0;
        ret->min = 0;
    } else {
        ret->maj = maj;
        ret->min = min;
    }
    
    return ret;
}