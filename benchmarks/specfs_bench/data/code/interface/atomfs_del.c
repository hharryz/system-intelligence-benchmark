#include "interface.h"

int atomfs_del(char* path[], char* name) {
    struct inode* parent = NULL;
    
    // Acquire lock on root and locate the parent directory
    lock(root_inum);
    parent = locate(root_inum, path);
    
    // If locate failed, return -1 (parent is NULL and locks are released)
    if (parent == NULL) {
        return -1;
    }
    
    // Check if deletion is allowed
    if (check_del(parent, name) != 0) {
        // check_del released the lock on parent in case of failure
        return -1;
    }
    
    // Delete the inode
    struct inode* deleted = inode_delete(parent, name);
    
    // If deletion failed, release parent's lock and return -1
    if (deleted == NULL) {
        unlock(parent);
        return -1;
    }
    
    // Dispose of the deleted inode
    dispose_inode(deleted);
    
    // Release parent's lock
    unlock(parent);
    
    return 0;
}