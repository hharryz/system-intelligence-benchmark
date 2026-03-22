#include "util.h"

struct inode* malloc_inode(int mode, unsigned maj, unsigned min) {
    struct inode *inode_ptr = (struct inode*)malloc(sizeof(struct inode));
    if (!inode_ptr) {
        return NULL;
    }
    
    // Zero-initialize the entire inode structure
    memset(inode_ptr, 0, sizeof(struct inode));
    
    // Set common fields
    inode_ptr->mode = mode;
    inode_ptr->maj = maj;
    inode_ptr->min = min;
    
    // Initialize MCS mutex
    inode_ptr->impl = mcs_mutex_create();
    
    // Handle directory vs regular file cases
    if (mode == DIR_MODE) {
        // Directory case: allocate and zero-initialize dirtb
        inode_ptr->dir = (struct dirtb*)malloc(sizeof(struct dirtb));
        if (!inode_ptr->dir) {
            free(inode_ptr->impl);
            free(inode_ptr);
            return NULL;
        }
        memset(inode_ptr->dir, 0, sizeof(struct dirtb));
        // file remains NULL (already zeroed)
    } else {
        // Regular file case: allocate and zero-initialize indextb
        inode_ptr->file = (struct indextb*)malloc(sizeof(struct indextb));
        if (!inode_ptr->file) {
            free(inode_ptr->impl);
            free(inode_ptr);
            return NULL;
        }
        memset(inode_ptr->file, 0, sizeof(struct indextb));
        // dir remains NULL (already zeroed)
    }
    
    return inode_ptr;
}