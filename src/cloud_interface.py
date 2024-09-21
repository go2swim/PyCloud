from abc import ABC, abstractmethod


class CloudInterface(ABC):
    @abstractmethod
    def check_upload(self):
        """Checks if folder is already uploaded,
        and if it's not, uploads it"""
        pass

    @abstractmethod
    def get_cloud_tree(self, folder_name, tree_list, root) -> list:
        """Recursively creates a list of folders.

        Args:
            folder_name — root folder for search
            tree_list — list of paths
            root — the temporary path of the directory which are then saved in the tree_list

        Returns:
            List of folders, such as [SYNC_FOLDER/child_folder/...]

        """
        pass

    @abstractmethod
    def upload_dir_on_cloud(self, upload_folders) -> None:
        """Downloads new folders that are on the computer, but not on the cloud"""
        pass

    @abstractmethod
    def update_dir_on_cloud(self, exact_folders) -> None:
        """Look folder and make a list of files: to delete, update and download"""
        pass

    @abstractmethod
    def remove_old_dir_on_cloud(self, remove_folders) -> None:
        """Remove cloud's folder that are on the cloud, but not on computer"""
        pass

    @abstractmethod
    def list_files(self, path) -> list:
        """Listing the root folder

        Returns:
            List of data for each object in FileData format

        """
        pass

    @abstractmethod
    def check_root_folder(self) -> bool:
        """Checks if the root folder exists on the cloud"""
        pass

    @abstractmethod
    def downloading_folders(self, download_folders) -> None:
        pass

    @abstractmethod
    def update_dir_on_pc(self, exact_folders) -> None:
        """Look folder and make a list of files: to delete, update and download"""
        pass
