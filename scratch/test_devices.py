import win32com.client
import pythoncom

def test_get_devices():
    pythoncom.CoInitialize()
    try:
        shell = win32com.client.Dispatch("Shell.Application")
        computer = shell.Namespace(17) # This PC
        print(f"Computer Namespace: {computer.Title if computer else 'None'}")
        if not computer:
            return
        
        for i in computer.Items():
            try:
                print(f"Name: {i.Name}, Path: {i.Path}")
            except Exception as e:
                print(f"Name: {i.Name}, Error getting path: {e}")

    except Exception as e:
        print(f"Main error: {e}")

if __name__ == "__main__":
    test_get_devices()
