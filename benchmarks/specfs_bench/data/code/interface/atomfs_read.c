#include "interface.h"

struct read_ret* atomfs_read(char* path[], unsigned size, unsigned offset) {
    struct inode* inum;
    
    // Acquire lock on root_inum as per pre-condition
    lock(root_inum);
    
    // Locate the target inode, which will release root_inum's lock and acquire target's lock
    inum = locate(root_inum, path);
    
    // Check if inode is valid
    if (inum == NULL) {
        return NULL;
    }
    
    // Check if inode is readable - check_file releases lock on failure
    if (check_file(inum) != 0) {
        return NULL;
    }
    
    // Perform the read operation
    struct read_ret* result = inode_read(inum, size, offset);
    
    // Release the lock on the inode as per post-condition (no lock owned)
    unlock(inum);
    
    return result;
}