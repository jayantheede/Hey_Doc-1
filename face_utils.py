"""
Face Recognition Helper Functions for Admin Authentication
Uses face_recognition library (dlib-based) for Face ID authentication
"""

try:
    import face_recognition
except ImportError:
    face_recognition = None
import numpy as np
from PIL import Image
import io
import base64
from typing import Tuple, Optional

def extract_face_encoding_from_base64(base64_image: str) -> Tuple[Optional[list], Optional[str]]:
    """
    Extract face embedding from base64-encoded image
    
    Args:
        base64_image: Base64-encoded image string
        
    Returns:
        Tuple of (face_encoding as list, error_message)
        face_encoding is 128-element list if successful, None if error
    """
    try:
        if face_recognition is None:
            return None, "Face recognition library is not installed."
        
        if not base64_image or len(base64_image) < 100:
            return None, "Invalid image data: Data is too short or empty."

        # Remove data URL prefix if present
        if "," in base64_image:
            base64_image = base64_image.split(",")[1]
        
        try:
            # Decode base64 to bytes
            image_bytes = base64.b64decode(base64_image)
            
            # Load image using PIL
            image_stream = io.BytesIO(image_bytes)
            image = Image.open(image_stream)
            
            # Basic validation of dimensions
            if image.width == 0 or image.height == 0:
                return None, "Invalid image dimensions: 0x0 detected."

        except Exception as pil_err:
            print(f"DEBUG FACE_UTILS: PIL Error - {pil_err}")
            return None, f"Could not identify or decode image file. (Technical details: {str(pil_err)})"
        
        # Convert to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Convert PIL image to numpy array
        image_array = np.array(image)
        
        # Find all faces in image
        face_locations = face_recognition.face_locations(image_array)
        
        if len(face_locations) == 0:
            return None, "No face detected in image. Please center your face in the frame."
        
        if len(face_locations) > 1:
            return None, "Multiple faces detected. Please ensure only one face is visible."
        
        # Get face encoding (128-dimensional vector)
        face_encodings = face_recognition.face_encodings(image_array, face_locations)
        
        if len(face_encodings) == 0:
            return None, "Could not process face features. Try better lighting."
        
        # Convert numpy array to list for JSON serialization
        return face_encodings[0].tolist(), None
        
    except Exception as e:
        print(f"DEBUG FACE_UTILS: Unexpected Error - {e}")
        return None, f"Error processing image: {str(e)}"

def extract_face_encoding_from_file(image_path: str) -> Tuple[Optional[list], Optional[str]]:
    """
    Extract face embedding from image file
    
    Args:
        image_path: Path to image file
        
    Returns:
        Tuple of (face_encoding as list, error_message)
    """
    try:
        if face_recognition is None:
            return None, "Face recognition library is not installed."
        # Load image directly
        image = face_recognition.load_image_file(image_path)
        
        # Find all faces
        face_locations = face_recognition.face_locations(image)
        
        if len(face_locations) == 0:
            return None, "No face detected in image"
        
        if len(face_locations) > 1:
            return None, "Multiple faces detected. Please ensure only one face is visible"
        
        # Get face encoding
        face_encodings = face_recognition.face_encodings(image, face_locations)
        
        if len(face_encodings) == 0:
            return None, "Could not encode face"
        
        return face_encodings[0].tolist(), None
        
    except Exception as e:
        return None, f"Error processing image file: {str(e)}"

def verify_face(live_encoding: list, stored_encoding: list, threshold: float = 0.6) -> Tuple[bool, float]:
    """
    Compare live face encoding with stored encoding
    
    Args:
        live_encoding: 128-element list from current capture
        stored_encoding: 128-element list from enrollment
        threshold: Similarity threshold (0.0-1.0), default 0.6
        
    Returns:
        Tuple of (is_match: bool, confidence: float)
        confidence is between 0.0 (no match) and 1.0 (perfect match)
    """
    try:
        if face_recognition is None:
            return False, 0.0
        if not live_encoding or not stored_encoding:
            return False, 0.0
        
        # Convert lists to numpy arrays
        live_enc = np.array(live_encoding)
        stored_enc = np.array(stored_encoding)
        
        # Calculate Euclidean distance between encodings
        distance = face_recognition.face_distance([stored_enc], live_enc)[0]
        
        # Convert distance to confidence score (0-1 range)
        # Lower distance = higher confidence
        confidence = 1.0 - distance
        
        # Clamp confidence to 0-1 range
        confidence = max(0.0, min(1.0, confidence))
        
        # Determine if match based on threshold
        is_match = confidence >= threshold
        
        return is_match, round(confidence, 3)
        
    except Exception as e:
        print(f"Error verifying face: {e}")
        return False, 0.0

def encrypt_face_encoding(encoding: list, encryption_key: str = None) -> str:
    """
    Encrypt face encoding for secure storage
    (Simple base64 encoding for now, can be enhanced with real encryption)
    
    Args:
        encoding: 128-element list
        encryption_key: Optional encryption key (not used in basic version)
        
    Returns:
        Base64-encoded string
    """
    try:
        # Convert list to JSON string then to bytes
        import json
        encoding_json = json.dumps(encoding)
        encoding_bytes = encoding_json.encode('utf-8')
        
        # Base64 encode
        encrypted = base64.b64encode(encoding_bytes).decode('utf-8')
        
        return encrypted
    except Exception as e:
        print(f"Error encrypting encoding: {e}")
        return ""

def decrypt_face_encoding(encrypted_encoding: str, encryption_key: str = None) -> Optional[list]:
    """
    Decrypt face encoding from storage
    
    Args:
        encrypted_encoding: Base64-encoded string
        encryption_key: Optional encryption key (not used in basic version)
        
    Returns:
        128-element list or None if error
    """
    try:
        # Base64 decode
        import json
        encoding_bytes = base64.b64decode(encrypted_encoding)
        encoding_json = encoding_bytes.decode('utf-8')
        
        # Parse JSON back to list
        encoding = json.loads(encoding_json)
        
        return encoding
    except Exception as e:
        print(f"Error decrypting encoding: {e}")
        return None

def validate_face_quality(base64_image: str) -> Tuple[bool, str]:
    """
    Validate image quality for face recognition
    
    Returns:
        Tuple of (is_valid: bool, message: str)
    """
    try:
        if face_recognition is None:
            return False, "Face recognition library is not installed."
        if "," in base64_image:
            base64_image = base64_image.split(",")[1]
        
        image_bytes = base64.b64decode(base64_image)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Check image size
        width, height = image.size
        if width < 200 or height < 200:
            return False, "Image too small. Please use at least 200x200 pixels"
        
        if width > 4000 or height > 4000:
            return False, "Image too large. Please use maximum 4000x4000 pixels"
        
        # Convert to numpy for face detection
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        image_array = np.array(image)
        
        # Check if face is detected
        face_locations = face_recognition.face_locations(image_array)
        
        if len(face_locations) == 0:
            return False, "No face detected. Please ensure your face is clearly visible"
        
        if len(face_locations) > 1:
            return False, "Multiple faces detected. Please ensure only one person is in frame"
        
        # Check face size (should be reasonable portion of image)
        top, right, bottom, left = face_locations[0]
        face_width = right - left
        face_height = bottom - top
        
        face_area_ratio = (face_width * face_height) / (width * height)
        
        if face_area_ratio < 0.05:
            return False, "Face too small in image. Please move closer to camera"
        
        if face_area_ratio > 0.9:
            return False, "Face too close. Please move back slightly"
        
        return True, "Face quality acceptable"
        
    except Exception as e:
        return False, f"Error validating image: {str(e)}"

# Test function (for development only)
def test_face_recognition():
    """Test the face recognition setup"""
    try:
        if face_recognition is None:
            print("❌ Face recognition library is NOT installed")
            return False
        # face_recognition is already imported globally at top of file
        print(f"✅ face_recognition library version: {face_recognition.__version__}")
        print("✅ Face recognition system ready")
        return True
    except Exception as e:
        print(f"❌ Face recognition test failed: {e}")
        return False

if __name__ == "__main__":
    # Run test when script is executed directly
    test_face_recognition()
