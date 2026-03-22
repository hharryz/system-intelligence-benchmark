#include "interface-util.h"

int check_src_exist_dst_delete(struct inode *srcdir, struct inode *dstdir, char *srcname, char *dstname) {
    struct inode *srcinode;
    struct inode *dstinode;
    int src_locked = 0;
    int dst_locked = 0;

    // Step 1: Check source existence
    srcinode = inode_find(srcdir, srcname);
    if (srcinode == NULL) {
        unlock2dir(srcdir, dstdir);
        return 1;
    }

    // Step 2: Check destination directory validity
    if (dstdir->mode != DIR_MODE || dstdir->size >= MAX_DIR_SIZE) {
        unlock2dir(srcdir, dstdir);
        return 1;
    }

    // Step 3: Check destination entry existence
    dstinode = inode_find(dstdir, dstname);
    
    if (dstinode != NULL) {
        if (srcinode == dstinode) {
            // Same inode: lock it once for dstinode (to be held for subsequent deletion)
            lock(dstinode);
            dst_locked = 1;
            // No further checks needed - validity is held per specification
        } else {
            // Acquire lock on srcinode
            lock(srcinode);
            src_locked = 1;
            
            // Acquire lock on dstinode
            lock(dstinode);
            dst_locked = 1;
            
            // Check type compatibility: both directories or both not directories
            int src_is_dir = (srcinode->mode == DIR_MODE);
            int dst_is_dir = (dstinode->mode == DIR_MODE);
            
            if (src_is_dir != dst_is_dir) {
                // Release all locks and return failure
                if (src_locked) unlock(srcinode);
                if (dst_locked) unlock(dstinode);
                unlock2dir(srcdir, dstdir);
                return 1;
            }
            
            // If dstinode is a directory (and not the same as srcinode), it must be empty
            if (dst_is_dir && dstinode->size != 0) {
                if (src_locked) unlock(srcinode);
                if (dst_locked) unlock(dstinode);
                unlock2dir(srcdir, dstdir);
                return 1;
            }
            
            // Release srcinode lock as per specification
            if (src_locked) unlock(srcinode);
            src_locked = 0;
        }
        // dstinode lock remains held in both cases (same or different inodes)
    }
    
    // All checks passed
    return 0;
}