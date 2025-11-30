import logging
import os
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
from config import WATERMARK_LOGO_PATH, WATERMARK_POSITION, WATERMARK_OPACITY

logger = logging.getLogger(__name__)

class WatermarkProcessor:
    def __init__(self):
        self.logo_path = WATERMARK_LOGO_PATH
        self.position = WATERMARK_POSITION  # 'top-left', 'top-right', 'bottom-left', 'bottom-right', 'center'
        self.opacity = WATERMARK_OPACITY  # 0-255
        
    async def add_watermark_to_image(self, image_path):
        """Add watermark to image"""
        try:
            if not os.path.exists(self.logo_path):
                logger.warning("Watermark logo not found, skipping watermark")
                return image_path
                
            # Open the original image
            original_image = Image.open(image_path)
            watermark = Image.open(self.logo_path)
            
            # Calculate position
            position = self._calculate_position(original_image.size, watermark.size)
            
            # Convert watermark to RGBA if not already
            if watermark.mode != 'RGBA':
                watermark = watermark.convert('RGBA')
                
            # Set opacity
            watermark = self._set_opacity(watermark, self.opacity)
            
            # Create a copy of original image
            watermarked_image = original_image.copy().convert('RGBA')
            
            # Paste watermark
            watermarked_image.paste(watermark, position, watermark)
            
            # Convert back to RGB if needed
            if original_image.mode == 'RGB':
                watermarked_image = watermarked_image.convert('RGB')
            
            # Save watermarked image
            output_path = image_path.replace('.', '_watermarked.')
            watermarked_image.save(output_path, quality=95)
            
            logger.info(f"Watermark added to image: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error adding watermark to image: {str(e)}")
            return image_path
            
    async def add_watermark_to_video(self, video_path):
        """Add watermark to video"""
        try:
            if not os.path.exists(self.logo_path):
                logger.warning("Watermark logo not found, skipping watermark")
                return video_path
                
            # Open video
            cap = cv2.VideoCapture(video_path)
            
            # Get video properties
            fps = int(cap.get(cv2.CAP_PROP_FPS))
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Load watermark
            watermark = cv2.imread(self.logo_path, cv2.IMREAD_UNCHANGED)
            if watermark is None:
                logger.error("Could not load watermark image")
                return video_path
                
            # Resize watermark (adjust size based on video dimensions)
            watermark = self._resize_watermark(watermark, width, height)
            
            # Calculate position
            position = self._calculate_video_position(width, height, watermark.shape[1], watermark.shape[0])
            
            # Prepare output video
            output_path = video_path.replace('.', '_watermarked.')
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
            
            frame_count = 0
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                    
                # Add watermark to frame
                frame_with_watermark = self._add_watermark_to_frame(frame, watermark, position)
                out.write(frame_with_watermark)
                
                frame_count += 1
                if frame_count % 30 == 0:  # Log every 30 frames
                    logger.info(f"Processed {frame_count}/{total_frames} frames")
            
            cap.release()
            out.release()
            
            logger.info(f"Watermark added to video: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error adding watermark to video: {str(e)}")
            return video_path
            
    def _calculate_position(self, image_size, watermark_size):
        """Calculate watermark position based on configuration"""
        img_width, img_height = image_size
        wm_width, wm_height = watermark_size
        
        margin = 20  # pixels from edge
        
        if self.position == 'top-left':
            return (margin, margin)
        elif self.position == 'top-right':
            return (img_width - wm_width - margin, margin)
        elif self.position == 'bottom-left':
            return (margin, img_height - wm_height - margin)
        elif self.position == 'bottom-right':
            return (img_width - wm_width - margin, img_height - wm_height - margin)
        elif self.position == 'center':
            return ((img_width - wm_width) // 2, (img_height - wm_height) // 2)
        else:  # default to bottom-right
            return (img_width - wm_width - margin, img_height - wm_height - margin)
            
    def _calculate_video_position(self, vid_width, vid_height, wm_width, wm_height):
        """Calculate position for video frames"""
        margin = 20
        
        if self.position == 'top-left':
            return (margin, margin)
        elif self.position == 'top-right':
            return (vid_width - wm_width - margin, margin)
        elif self.position == 'bottom-left':
            return (margin, vid_height - wm_height - margin)
        elif self.position == 'bottom-right':
            return (vid_width - wm_width - margin, vid_height - wm_height - margin)
        elif self.position == 'center':
            return ((vid_width - wm_width) // 2, (vid_height - wm_height) // 2)
        else:
            return (vid_width - wm_width - margin, vid_height - wm_height - margin)
            
    def _set_opacity(self, image, opacity):
        """Set opacity of watermark"""
        if image.mode != 'RGBA':
            return image
            
        # Create a new image with adjusted alpha
        alpha = image.split()[3]
        alpha = alpha.point(lambda p: p * opacity // 255)
        image.putalpha(alpha)
        return image
        
    def _resize_watermark(self, watermark, video_width, video_height):
        """Resize watermark based on video dimensions"""
        # Resize to 10% of video width or height (whichever is smaller)
        max_size = min(video_width, video_height) * 0.15
        
        h, w = watermark.shape[:2]
        scale = min(max_size / w, max_size / h)
        
        new_w = int(w * scale)
        new_h = int(h * scale)
        
        return cv2.resize(watermark, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
    def _add_watermark_to_frame(self, frame, watermark, position):
        """Add watermark to a single video frame"""
        x, y = position
        h, w = watermark.shape[:2]
        
        # Extract the alpha channel from watermark
        if watermark.shape[2] == 4:
            alpha = watermark[:, :, 3] / 255.0
            watermark_rgb = watermark[:, :, :3]
        else:
            alpha = np.ones((h, w)) * (self.opacity / 255.0)
            watermark_rgb = watermark
            
        # Ensure we don't go out of bounds
        if y + h > frame.shape[0] or x + w > frame.shape[1]:
            logger.warning("Watermark position out of bounds, adjusting...")
            return frame
            
        # Blend watermark with frame
        for c in range(3):
            frame[y:y+h, x:x+w, c] = (
                alpha * watermark_rgb[:, :, c] + 
                (1 - alpha) * frame[y:y+h, x:x+w, c]
            )
            
        return frame
        
    def cleanup_temp_files(self, *file_paths):
        """Clean up temporary watermarked files"""
        for file_path in file_paths:
            if file_path and os.path.exists(file_path) and 'watermarked' in file_path:
                try:
                    os.remove(file_path)
                    logger.info(f"Cleaned up temporary file: {file_path}")
                except Exception as e:
                    logger.warning(f"Could not delete temp file {file_path}: {str(e)}")
