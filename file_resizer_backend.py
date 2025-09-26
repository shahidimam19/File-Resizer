import os
from io import BytesIO
from PIL import Image
import fitz  # PyMuPDF

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
        img_format = img.format
        original_width, original_height = img.size
        
        # Calculate new dimensions based on the aspect ratio without cropping
        if aspect_ratio:
            ratio_w, ratio_h = aspect_ratio
            if ratio_w > 0 and ratio_h > 0:
                # Resize to the new aspect ratio, which will distort the image but not crop it.
                new_height = int(original_width * (ratio_h / ratio_w))
                img = img.resize((original_width, new_height), Image.Resampling.LANCZOS)
        
        # Iteratively reduce quality and dimensions to meet the target size
        current_width, current_height = img.size
        quality = 95
        
        while True:
            buffer = BytesIO()
            img.save(buffer, format=img_format, quality=quality)
            current_size_kb = buffer.tell() / 1024
            
            if current_size_kb <= target_kb or quality <= 10:
                with open(output_path, 'wb') as f:
                    f.write(buffer.getvalue())
                return True
            
            # Reduce quality first
            if quality > 60:
                quality -= 5
            else:
                # If quality is low and size is still too large, reduce dimensions
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
    Resizes a PDF by re-compressing its contents to a target file size.
    
    Args:
        input_path (str): The path to the input PDF file.
        output_path (str): The path to save the resized PDF.
        target_kb (int): The target file size in kilobytes.
    
    Returns:
        bool: True if the resize was successful, False otherwise.
    """
    try:
        doc = fitz.open(input_path)
        current_size_kb = os.path.getsize(input_path) / 1024
        
        # If the file is already small enough, no need to resize
        if current_size_kb <= target_kb:
            # We still save a copy to the output path for consistency
            doc.save(output_path)
            doc.close()
            return True

        new_doc = fitz.open()
        for page_num in range(len(doc)):
            page = doc.load_page(page_num)
            pix = page.get_pixmap(matrix=fitz.Matrix(0.7, 0.7)) # Scale down images
            new_page = new_doc.new_page(width=pix.width, height=pix.height)
            new_page.insert_image(new_page.rect, pixmap=pix)
        
        # Save the new document with garbage collection and compression
        new_doc.save(output_path, garbage=4, clean=True, deflate=True)
        new_doc.close()
        doc.close()
        return True

    except Exception as e:
        print(f"Error resizing PDF: {e}")
        return False
