#include "interface.h"

char **atomfs_readdir(char *path[]) {
    struct inode *target;
    
    // Lock root_inum before calling locate
    lock(root_inum);
    
    // Traverse path to find target inode
    target = locate(root_inum, path);
    
    // If locate failed, unlock root_inum and return NULL
    if (target == NULL) {
        unlock(root_inum);
        return NULL;
    }
    
    // Check if target is a directory
    if (check_dir(target) != 0) {
        // check_dir already released the lock on target if it failed
        return NULL;
    }
    
    // At this point, target is locked and is a valid directory
    // Allocate memory for directory content (size + 1 for NULL-terminated array)
    char **dircontent = malloc_dir_content(target->size + 1);
    if (dircontent == NULL) {
        unlock(target);
        return NULL;
    }
    
    // Fill the directory content
    fill_dir(target, dircontent);
    
    // Release the lock on target
    unlock(target);
    
    return dircontent;
}