#!/usr/bin/env python3

"""
This file adds the missing get_camera_info method to the CameraManager class.
"""

def add_get_camera_info_method():
    """
    Add the get_camera_info method to the camera_manager.py file.
    """
    with open("camera_manager.py", "r") as f:
        lines = f.readlines()
    
    # Find the location where to add our new method
    # After the get_connected_cameras method
    for i, line in enumerate(lines):
        if "def get_connected_cameras" in line:
            # Find the end of this method to place our new method
            indent_level = len(line) - len(line.lstrip())
            for j in range(i+1, len(lines)):
                if lines[j].strip() and len(lines[j]) - len(lines[j].lstrip()) <= indent_level:
                    # Found the end of the method
                    insert_position = j
                    break
            else:
                # Reached end of file
                insert_position = len(lines)
            break
    else:
        print("Error: Could not find get_connected_cameras method in the file.")
        return False
    
    # Create the new method
    get_camera_info_method = [
        "\n",
        "    def get_camera_info(self, port: str) -> Optional[CameraInfo]:\n",
        "        \"\"\"\n",
        "        Get camera information by port.\n",
        "        \n",
        "        Args:\n",
        "            port: Camera port\n",
        "            \n",
        "        Returns:\n",
        "            CameraInfo object or None if camera not found\n",
        "        \"\"\"\n",
        "        return self.cameras.get(port)\n",
        "\n"
    ]
    
    # Insert the new method
    for i, line in enumerate(get_camera_info_method):
        lines.insert(insert_position + i, line)
    
    # Write the modified file
    with open("camera_manager.py", "w") as f:
        f.writelines(lines)
    
    print("Successfully added get_camera_info method to camera_manager.py")
    return True

if __name__ == "__main__":
    add_get_camera_info_method()