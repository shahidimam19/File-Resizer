import os
import uuid 
from io import BytesIO
from PIL import Image
import fitz  # PyMuPDF

# --- Helper function for robust PyMuPDF compression ---

def _get_compressed_jpeg_bytes(pix: fitz.Pixmap, quality: int) -> bytes:
    """
    Saves a Pixmap to a temporary file path with specified JPEG quality, reads the
    bytes, and deletes the temporary file. This works around PyMuPDF's low-level
    C API limitations when saving to BytesIO with quality parameters.
    
    Args:
        pix (fitz.Pixmap): The PyMuPDF Pixmap object to compress.
        quality (int): JPEG quality (0-100).
        
    Returns:
        bytes: The compressed JPEG data.
    """
    # Create a unique temporary filename in the current working directory
    temp_filename = f"temp_comp_img_{uuid.uuid4()}.jpg"
    
    try:
        # Save to the temporary file path, using jpg_quality
        pix.save(temp_filename, "jpeg", jpg_quality=quality)
        
        # Read the resulting compressed file content
        with open(temp_filename, "rb") as f:
            img_bytes = f.read()
        
        return img_bytes
        
    finally:
        # Ensure the temporary file is deleted, even if an error occurred
        if os.path.exists(temp_filename):
            os.remove(temp_filename)
            
# --- Core PDF Resizing Logic (using Binary Search) ---

def _rasterize_to_target(input_path: str, output_path: str, target_kb: int, scale_factor: float = 0.8) -> bool:
    """
    Rasterize PDF pages to images and uses binary search on JPEG quality
    to find the best quality that results in a file size <= target_kb.

    Args:
        input_path (str): The path to the input PDF file.
        output_path (str): The final destination path for the resized PDF.
        target_kb (int): The target file size in kilobytes.
        scale_factor (float): The factor by which to scale down the page resolution.

    Returns:
        bool: True if a suitable file was created, False otherwise.
    """
    doc_original = fitz.open(input_path)
    # UPDATED: Changed upper limit of search range from 95 to 99
    low, high = 30, 99  # JPEG quality range (PyMuPDF usually handles 1-100)
    best_size = float("inf")
    best_file_to_keep = None
    tested_temp_files = []

    try:
        while low <= high:
            mid = (low + high) // 2
            # Create a unique temporary path for this quality test
            temp_path = output_path + f".q{mid}.tmp"
            tested_temp_files.append(temp_path)

            doc_new = fitz.open()
            for page_num in range(len(doc_original)):
                page = doc_original.load_page(page_num)
                # Create the transformation matrix based on scale factor
                matrix = fitz.Matrix(scale_factor, scale_factor)
                
                # Get the rasterized page at reduced resolution
                pix = page.get_pixmap(matrix=matrix, alpha=False)

                # Save image as JPEG with given quality (uses _get_compressed_jpeg_bytes for cleanup)
                img_bytes = _get_compressed_jpeg_bytes(pix, mid)
                
                # Insert the compressed image into the new document
                new_page = doc_new.new_page(width=pix.width, height=pix.height)
                new_page.insert_image(new_page.rect, stream=img_bytes)

            # Save the test PDF
            doc_new.save(temp_path, garbage=4, deflate=True, clean=True)
            doc_new.close()

            size_kb = os.path.getsize(temp_path) / 1024
            print(f"Test quality {mid} → {size_kb:.2f} KB (Target: {target_kb} KB)")

            # Track best candidate (closest to target but not exceeding)
            if size_kb <= target_kb:
                if abs(size_kb - target_kb) < abs(best_size - target_kb):
                    best_size = size_kb
                    best_file_to_keep = temp_path
                # Since we are below the target, we can try higher quality (larger size)
                low = mid + 1
            else:
                # We exceeded the target, so we must reduce quality (smaller size)
                high = mid - 1
        
        doc_original.close()

        # If we found a good candidate, rename it to the final output path
        if best_file_to_keep:
            # First, clean up all the other temporary test files
            for test_file in tested_temp_files:
                if test_file != best_file_to_keep and os.path.exists(test_file):
                    os.remove(test_file)
            
            # Rename the best candidate to the final output path
            os.rename(best_file_to_keep, output_path)
            print(f"Final size achieved: {os.path.getsize(output_path) / 1024:.2f} KB")
            return True
        
        # If no suitable file was found in the 30-99 range
        return False
        
    except Exception as e:
        print(f"Error during PDF rasterization and binary search: {e}")
        doc_original.close()
        return False
    finally:
        # Ensure all temporary test files are cleaned up upon exit, regardless of success/failure
        for test_file in tested_temp_files:
            if os.path.exists(test_file) and test_file != output_path:
                try:
                    os.remove(test_file)
                except:
                    pass # Ignore errors during cleanup

# --- Existing resize_image function (no change) ---

def resize_image(input_path: str, output_path: str, target_kb: int, aspect_ratio: tuple = None) -> bool:
    """
    Resizes an image to a target file size in KB, with an optional aspect ratio resize.
    
    Args:
        input_path (str): The path to the input image file.
        output_path (str): The path to save the resized image.
        target_kb (int): The target file size in kilobytes.
        aspect_ratio (tuple, optional): A tuple (W, H) for the desired aspect ratio. Defaults to None.
    
    Returns:
        bool: True if the resize was successful, False otherwise.
    """
    try:
        img = Image.open(input_path)
        img_format = img.format if img.format in ['JPEG', 'PNG'] else 'JPEG'
        original_width, original_height = img.size
        
        if aspect_ratio:
            ratio_w, ratio_h = aspect_ratio
            if ratio_w > 0 and ratio_h > 0:
                new_height = int(original_width * (ratio_h / ratio_w))
                img = img.resize((original_width, new_height), Image.Resampling.LANCZOS)
        
        current_width, current_height = img.size
        quality = 95
        
        while True:
            buffer = BytesIO()
            save_format = 'JPEG' if img_format != 'PNG' else 'PNG'
            
            img.save(buffer, format=save_format, quality=quality, optimize=True)
            current_size_kb = buffer.tell() / 1024
            
            if current_size_kb <= target_kb or quality <= 10:
                with open(output_path, 'wb') as f:
                    f.write(buffer.getvalue())
                return True
            
            if quality > 60:
                quality -= 5
            else:
                current_width = int(current_width * 0.9)
                current_height = int(current_height * 0.9)
                if current_width == 0 or current_height == 0:
                    return False
                img = img.resize((current_width, current_height), Image.Resampling.LANCZOS)
                
    except Exception as e:
        print(f"Error resizing image: {e}")
        return False


def resize_pdf(input_path: str, output_path: str, target_kb: int) -> bool:
    """
    Resizes a PDF using a two-pass strategy:
    1. Non-destructive: Compress embedded images and optimize structure.
    2. Destructive (Fallback): Rasterize and downscale using binary search on quality.
    
    Args:
        input_path (str): The path to the input PDF file.
        output_path (str): The path to save the resized PDF.
        target_kb (int): The target file size in kilobytes.
    
    Returns:
        bool: True if the resize was successful, False otherwise.
    """
    
    # --- PASS 1: Non-destructive Image Compression & Optimization ---
    try:
        doc = fitz.open(input_path)
        image_quality = 85
        
        # 1a. Compress existing images in place
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            for img in page.get_images(full=True):
                xref = img[0]
                if xref > 0:
                    try:
                        pix = fitz.Pixmap(doc, xref)
                        if pix.n >= 4:  
                            pix = fitz.Pixmap(fitz.csRGB, pix)
                        
                        img_bytes = _get_compressed_jpeg_bytes(pix, image_quality)
                        
                        doc.update_image(xref, img_bytes)
                        pix = None
                    except Exception as e:
                        print(f"Skipping problematic image {xref} on page {page_num}: {e}")
                        continue
                        
        # 1b. Save with aggressive general PDF optimizations
        doc.save(output_path, garbage=4, deflate=True, clean=True)
        doc.close()
        
        current_size_kb = os.path.getsize(output_path) / 1024
        print(f"Pass 1 (Image Comp/Opt) size: {current_size_kb:.2f} KB (Target: {target_kb} KB)")
        
        if current_size_kb <= target_kb:
            return True

        # --- PASS 2: Destructive Rasterization/Downscaling Fallback (using Binary Search) ---
        print("Pass 1 failed to reach target. Applying aggressive rasterization with binary search.")
        
        # If Pass 1 file exists, delete it before starting Pass 2, as Pass 2 will create the final file
        if os.path.exists(output_path):
            os.remove(output_path)

        # Call the new binary search function
        return _rasterize_to_target(input_path, output_path, target_kb)

    except Exception as e:
        error_message = f"PDF processing failed: {e}"
        print(f"Error resizing PDF: {e}")
        
        # Cleanup any partial files
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass

        return False
