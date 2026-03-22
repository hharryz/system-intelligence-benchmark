#include "interface.h"

int atomfs_rename(char* srcpath[], char* dstpath[], char* srcname, char* dstname) {
    char** common_path = calculate(srcpath, dstpath);
    int common_len = getlen(common_path);
    
    // Phase 1: Traverse the Common Path
    lock(root_inum);
    struct inode* parent = locate(root_inum, common_path);
    if (parent == NULL) {
        free_path(common_path);
        return -1;
    }
    
    // Phase 2: Traverse Remaining Paths
    char** src_remaining = &srcpath[common_len];
    char** dst_remaining = &dstpath[common_len];
    
    struct inode* srcdir = locate_hold(parent, src_remaining);
    if (srcdir == NULL) {
        unlock(parent);
        free_path(common_path);
        return -1;
    }
    
    struct inode* dstdir = locate_hold(parent, dst_remaining);
    if (dstdir == NULL) {
        unlock(parent);
        unlock(srcdir);
        free_path(common_path);
        return -1;
    }
    
    // Release parent lock if it's not srcdir or dstdir
    check_unlock(parent, srcdir, dstdir);
    free_path(common_path);
    
    // Phase 3: Checks and Operations
    int check_result = check_src_exist_dst_delete(srcdir, dstdir, srcname, dstname);
    if (check_result != 0) {
        // check_src_exist_dst_delete already released all necessary locks on failure
        return -1;
    }
    
    // Delete source from srcdir
    struct inode* srcinode = inode_delete(srcdir, srcname);
    if (srcinode == NULL) {
        unlock2dir(srcdir, dstdir);
        return -1;
    }
    
    // Delete destination from dstdir (if exists)
    struct inode* dstinode = inode_delete(dstdir, dstname);
    
    // Insert source inode into dstdir with dstname
    int insert_result = inode_insert(dstdir, srcinode, dstname);
    if (insert_result != 0) {
        // If insert fails, restore srcinode to srcdir
        inode_insert(srcdir, srcinode, srcname);
        if (dstinode != NULL) {
            unlock(dstinode);
            dispose_inode(dstinode);
        }
        unlock2dir(srcdir, dstdir);
        return -1;
    }
    
    // Dispose of old destination inode if it existed and insert succeeded
    if (dstinode != NULL) {
        unlock(dstinode);
        dispose_inode(dstinode);
    }
    
    unlock2dir(srcdir, dstdir);
    return 0;
}