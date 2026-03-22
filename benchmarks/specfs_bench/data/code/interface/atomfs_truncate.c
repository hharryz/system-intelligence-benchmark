#include "interface.h"

int atomfs_truncate(char* path[], unsigned offset) {
    struct inode* target;
    
    // Pre-condition: no lock is owned
    // Check if path is valid
    if (path == NULL) {
        return -1;
    }
    
    // Check if root_inum is valid
    if (root_inum == NULL) {
        return -1;
    }
    
    // Check if offset exceeds maximum file size
    if (offset > MAX_FILE_SIZE) {
        return -1;
    }
    
    // Start from root_inum and traverse the path
    // root_inum must be valid and initialized (invariant)
    lock(root_inum);
    target = locate(root_inum, path);
    
    // If locate returns NULL, path traversal failed
    if (target == NULL) {
        return -1;
    }
    
    // Check if the target is a regular file
    if (check_file(target) != 0) {
        // check_file releases the lock on failure
        return -1;
    }
    
    // Truncate the file to the specified offset
    inode_truncate(target, offset);
    
    // Release the lock on target
    unlock(target);
    
    // Post-condition: no lock is owned
    return 0;
}