import sys
import os

# Add current directory to path so we can import capture
sys.path.append(os.getcwd())

try:
    from capture import capture_screen_base64
    import base64

    print("Attempting to capture screen...")
    b64_str = capture_screen_base64(scale=0.5)
    
    if not b64_str:
        print("ERROR: capture_screen_base64 returned empty string")
        sys.exit(1)

    print(f"Capture successful. Size: {len(b64_str)} chars")
    
    # Decode and save to verify it's a valid image
    img_data = base64.b64decode(b64_str)
    with open("verify_capture.jpg", "wb") as f:
        f.write(img_data)
    
    print("Saved 'verify_capture.jpg'. Please check if this image is valid.")

except Exception as e:
    print(f"CRITICAL ERROR: {e}")
    import traceback
    traceback.print_exc()
