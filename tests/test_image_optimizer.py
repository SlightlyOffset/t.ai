import os
import unittest
import tempfile
from unittest.mock import patch, MagicMock
from PIL import Image

import engines.image_optimizer as io_module


class TestImageOptimizer(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory structure for tests
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_dir = os.path.abspath(self.temp_dir_obj.name)
        
        self.cache_patcher = patch('engines.image_optimizer.CACHE_DIR', self.temp_dir)
        self.download_patcher = patch('engines.image_optimizer.DOWNLOAD_DIR', os.path.join(self.temp_dir, "downloads"))
        
        self.mock_cache_dir = self.cache_patcher.start()
        self.mock_download_dir = self.download_patcher.start()
        
        os.makedirs(self.mock_cache_dir, exist_ok=True)
        os.makedirs(self.mock_download_dir, exist_ok=True)
        
        # Create a test high-res image (1000x1000)
        self.large_image_path = os.path.join(self.mock_cache_dir, "test_large.png")
        img = Image.new("RGB", (1000, 1000), color="red")
        img.save(self.large_image_path)
        
        # Create a test low-res image (100x100)
        self.small_image_path = os.path.join(self.mock_cache_dir, "test_small.png")
        img_small = Image.new("RGB", (100, 100), color="blue")
        img_small.save(self.small_image_path)

    def tearDown(self):
        self.cache_patcher.stop()
        self.download_patcher.stop()
        try:
            self.temp_dir_obj.cleanup()
        except Exception:
            pass

    def test_no_optimization_needed_for_small_images(self):
        # Small image (100x100) with max_dim=500 should return the original path directly
        res = io_module.get_or_create_optimized_image(self.small_image_path, max_dim=500)
        self.assertEqual(res, os.path.abspath(self.small_image_path))

    def test_optimization_downscales_large_images(self):
        # Large image (1000x1000) with max_dim=500 should return a cached optimized image path
        res = io_module.get_or_create_optimized_image(self.large_image_path, max_dim=500)
        self.assertNotEqual(res, os.path.abspath(self.large_image_path))
        self.assertTrue(os.path.exists(res))
        
        # Verify optimized image size is indeed downscaled
        with Image.open(res) as img:
            w, h = img.size
            self.assertEqual(w, 500)
            self.assertEqual(h, 500)

        # Re-running optimization should hit the cache
        res_cached = io_module.get_or_create_optimized_image(self.large_image_path, max_dim=500)
        self.assertEqual(res_cached, res)

    @patch("urllib.request.urlopen")
    @patch("requests.get")
    def test_download_and_optimize_remote_image(self, mock_get, mock_urlopen):
        # Mock urllib.request.urlopen to return a valid response containing small image bytes
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "image/png"}
        
        # Write small image to bytes
        import io
        img_bytes = io.BytesIO()
        Image.new("RGB", (120, 120), color="green").save(img_bytes, format="PNG")
        mock_response.read.return_value = img_bytes.getvalue()
        
        mock_urlopen.return_value.__enter__.return_value = mock_response

        # Test download
        url = "https://example.com/avatar_test.png"
        res = io_module.get_or_create_optimized_image(url, max_dim=500)
        
        # It should download it, determine it's <= 500px, and return the downloaded file path
        self.assertTrue(res.startswith(io_module.DOWNLOAD_DIR))
        self.assertTrue(os.path.exists(res))
        with Image.open(res) as img:
            w, h = img.size
            self.assertEqual(w, 120)
            self.assertEqual(h, 120)

    @patch("urllib.request.urlopen")
    @patch("requests.get")
    def test_download_fallback_to_requests(self, mock_get, mock_urlopen):
        # Mock urllib to fail
        mock_urlopen.side_effect = Exception("Urllib down")
        
        # Mock requests.get to return a valid response containing small image bytes
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "image/png"}
        
        # Write small image to bytes
        import io
        img_bytes = io.BytesIO()
        Image.new("RGB", (120, 120), color="green").save(img_bytes, format="PNG")
        mock_response.content = img_bytes.getvalue()
        
        mock_get.return_value = mock_response

        # Test download
        url = "https://example.com/avatar_test.png"
        res = io_module.get_or_create_optimized_image(url, max_dim=500)
        
        self.assertTrue(res.startswith(io_module.DOWNLOAD_DIR))
        self.assertTrue(os.path.exists(res))
        with Image.open(res) as img:
            w, h = img.size
            self.assertEqual(w, 120)
            self.assertEqual(h, 120)

    @patch("urllib.request.urlopen")
    @patch("requests.get")
    def test_failed_download_falls_back_to_url(self, mock_get, mock_urlopen):
        mock_urlopen.side_effect = Exception("Urllib down")
        mock_get.side_effect = Exception("Network down")
        url = "https://example.com/failed_test.png"
        res = io_module.get_or_create_optimized_image(url, max_dim=500)
        self.assertEqual(res, url)

    @patch("urllib.request.urlopen")
    @patch("requests.get")
    def test_corrupted_download_returns_original_url(self, mock_get, mock_urlopen):
        # Mock HTML landing page content (not an image) for both
        mock_response_urllib = MagicMock()
        mock_response_urllib.status = 200
        mock_response_urllib.headers = {"Content-Type": "text/html"}
        mock_response_urllib.read.return_value = b"<html>Landing Page</html>"
        mock_urlopen.return_value.__enter__.return_value = mock_response_urllib

        mock_response_requests = MagicMock()
        mock_response_requests.status_code = 200
        mock_response_requests.headers = {"Content-Type": "text/html"}
        mock_response_requests.content = b"<html>Landing Page</html>"
        mock_get.return_value = mock_response_requests

        url = "https://example.com/html_landing_page.png"
        res = io_module.get_or_create_optimized_image(url, max_dim=500)
        
        # It should detect HTML content type and not download it, returning the original URL
        self.assertEqual(res, url)


if __name__ == "__main__":
    unittest.main()
