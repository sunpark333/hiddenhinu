# file name: video_watermark.py
# file content begin
import os
import tempfile
import logging
from PIL import Image, ImageDraw, ImageFont
import subprocess

logger = logging.getLogger(__name__)

class VideoWatermark:
    def __init__(self, logo_path="channel_logo.png", position="bottom-right", opacity=0.7):
        """
        Initialize video watermark processor
        
        Args:
            logo_path: Path to channel logo image
            position: Position of watermark (bottom-right, bottom-left, top-right, top-left)
            opacity: Opacity of watermark (0.0 to 1.0)
        """
        self.logo_path = logo_path
        self.position = position
        self.opacity = opacity
        
        # Check if logo exists
        if not os.path.exists(self.logo_path):
            logger.warning(f"Logo file not found: {self.logo_path}")
            # Create a default logo placeholder
            self._create_default_logo()
    
    def _create_default_logo(self):
        """Create a default logo if not found"""
        try:
            from config import YOUR_CHANNEL_ID
            logo_text = f"Channel {YOUR_CHANNEL_ID}"
        except:
            logo_text = "My Channel"
            
        img = Image.new('RGBA', (200, 100), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("arial.ttf", 20)
        except:
            font = ImageFont.load_default()
            
        # Draw semi-transparent background
        draw.rectangle([0, 0, 200, 100], fill=(0, 0, 0, 150))
        
        # Draw text
        draw.text((10, 40), logo_text, fill=(255, 255, 255, 255), font=font)
        
        img.save(self.logo_path)
        logger.info(f"Created default logo at: {self.logo_path}")
    
    def add_watermark_to_video(self, input_video_path, output_video_path=None):
        """
        Add watermark to video using FFmpeg
        
        Args:
            input_video_path: Path to input video
            output_video_path: Path for output video (optional)
            
        Returns:
            Path to watermarked video
        """
        if not os.path.exists(input_video_path):
            logger.error(f"Input video not found: {input_video_path}")
            return input_video_path
        
        # If output path not provided, create temp file
        if not output_video_path:
            temp_dir = tempfile.gettempdir()
            output_video_path = os.path.join(temp_dir, f"watermarked_{os.path.basename(input_video_path)}")
        
        # Determine position coordinates
        if self.position == "bottom-right":
            position_filter = "overlay=W-w-10:H-h-10"
        elif self.position == "bottom-left":
            position_filter = "overlay=10:H-h-10"
        elif self.position == "top-right":
            position_filter = "overlay=W-w-10:10"
        elif self.position == "top-left":
            position_filter = "overlay=10:10"
        else:
            position_filter = "overlay=W-w-10:H-h-10"  # default bottom-right
        
        try:
            # First, scale logo if needed
            scaled_logo_path = os.path.join(tempfile.gettempdir(), "scaled_logo.png")
            
            # Get video dimensions
            cmd_probe = [
                'ffprobe', '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width,height',
                '-of', 'csv=p=0',
                input_video_path
            ]
            
            result = subprocess.run(cmd_probe, capture_output=True, text=True)
            if result.returncode == 0:
                dimensions = result.stdout.strip().split(',')
                if len(dimensions) == 2:
                    video_width = int(dimensions[0])
                    video_height = int(dimensions[1])
                    
                    # Scale logo to 15% of video width
                    logo_width = int(video_width * 0.15)
                    
                    # Scale logo maintaining aspect ratio
                    img = Image.open(self.logo_path)
                    aspect_ratio = img.width / img.height
                    logo_height = int(logo_width / aspect_ratio)
                    
                    # Resize logo
                    img_resized = img.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
                    img_resized.save(scaled_logo_path)
                    
                    logger.info(f"Scaled logo to: {logo_width}x{logo_height}")
            
            # Add watermark with FFmpeg
            cmd = [
                'ffmpeg',
                '-i', input_video_path,
                '-i', scaled_logo_path,
                '-filter_complex',
                f'[1]format=rgba,colorchannelmixer=aa={self.opacity}[logo];[0][logo]{position_filter}',
                '-codec:a', 'copy',
                '-y',  # Overwrite output file if exists
                output_video_path
            ]
            
            logger.info(f"Adding watermark to video: {input_video_path}")
            
            # Run FFmpeg command
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                logger.info(f"Watermarked video saved to: {output_video_path}")
                
                # Clean up scaled logo
                if os.path.exists(scaled_logo_path):
                    os.remove(scaled_logo_path)
                
                return output_video_path
            else:
                logger.error(f"FFmpeg error: {result.stderr}")
                return input_video_path
                
        except Exception as e:
            logger.error(f"Error adding watermark: {str(e)}")
            return input_video_path
    
    def add_watermark_to_image(self, input_image_path, output_image_path=None):
        """
        Add watermark to image
        
        Args:
            input_image_path: Path to input image
            output_image_path: Path for output image (optional)
            
        Returns:
            Path to watermarked image
        """
        if not os.path.exists(input_image_path):
            logger.error(f"Input image not found: {input_image_path}")
            return input_image_path
        
        if not os.path.exists(self.logo_path):
            logger.error(f"Logo not found: {self.logo_path}")
            return input_image_path
        
        try:
            # Open images
            base_image = Image.open(input_image_path).convert("RGBA")
            logo_image = Image.open(self.logo_path).convert("RGBA")
            
            # Calculate logo size (15% of base image width)
            logo_width = int(base_image.width * 0.15)
            aspect_ratio = logo_image.width / logo_image.height
            logo_height = int(logo_width / aspect_ratio)
            
            # Resize logo
            logo_resized = logo_image.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
            
            # Apply opacity
            if self.opacity < 1.0:
                alpha = logo_resized.split()[3]
                alpha = alpha.point(lambda p: p * self.opacity)
                logo_resized.putalpha(alpha)
            
            # Calculate position
            if self.position == "bottom-right":
                position = (base_image.width - logo_width - 10, base_image.height - logo_height - 10)
            elif self.position == "bottom-left":
                position = (10, base_image.height - logo_height - 10)
            elif self.position == "top-right":
                position = (base_image.width - logo_width - 10, 10)
            elif self.position == "top-left":
                position = (10, 10)
            else:
                position = (base_image.width - logo_width - 10, base_image.height - logo_height - 10)
            
            # Create transparent layer for logo
            transparent = Image.new('RGBA', base_image.size, (0, 0, 0, 0))
            transparent.paste(logo_resized, position)
            
            # Composite images
            watermarked = Image.alpha_composite(base_image, transparent)
            
            # If output path not provided, overwrite input
            if not output_image_path:
                output_image_path = input_image_path
                # Convert back to RGB if needed
                if input_image_path.lower().endswith('.jpg') or input_image_path.lower().endswith('.jpeg'):
                    watermarked = watermarked.convert('RGB')
            
            watermarked.save(output_image_path)
            logger.info(f"Watermarked image saved to: {output_image_path}")
            
            return output_image_path
            
        except Exception as e:
            logger.error(f"Error adding watermark to image: {str(e)}")
            return input_image_path

# Helper function to check if FFmpeg is available
def check_ffmpeg_available():
    """Check if FFmpeg is installed and available"""
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True)
        return result.returncode == 0
    except FileNotFoundError:
        return False

# Create default logo if needed
def create_default_logo():
    """Create a default channel logo"""
    watermark = VideoWatermark()
    return watermark.logo_path
# file content end
