#include "path.h"

struct inode* locate_hold(struct inode *cur, char *path[]) {
    struct inode *next_inum;
    
    // If path is empty, return cur (which is already locked)
    if (path[0] == NULL) {
        return cur;
    }
    
    // Find the next inode in the directory
    next_inum = inode_find(cur, path[0]);
    
    // If not found, retain lock on cur and return NULL
    if (next_inum == NULL) {
        return NULL;
    }
    
    // Acquire lock on next_inum
    lock(next_inum);
    
    // Now traverse the remaining path components manually
    // to ensure cur's lock is retained throughout
    char **p = &path[1];
    struct inode *current = next_inum;
    
    // Traverse remaining path components
    while (*p != NULL) {
        struct inode *child = inode_find(current, *p);
        if (child == NULL) {
            // Release the lock on current (which was acquired by us or previously)
            // but note: current might be next_inum (locked by us) or a later inode
            unlock(current);
            return NULL;
        }
        
        // Lock the child before releasing current (lock coupling)
        lock(child);
        unlock(current);
        
        current = child;
        p++;
    }
    
    // At this point, current is the target inode, locked
    // cur remains locked as required
    return current;
}