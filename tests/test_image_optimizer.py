import os
import unittest
from unittest.mock import patch, MagicMock
from PIL import Image
from engines.image_optimizer import (
    get_or_create_optimized_image,
    download_image,
    CACHE_DIR,
    DOWNLOAD_DIR
)


class TestImageOptimizer(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory structure for tests
        os.makedirs(CACHE_DIR, exist_ok=True)
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        
        # Create a test high-res image (1000x1000)
        self.large_image_path = os.path.join(CACHE_DIR, "test_large.png")
        img = Image.new("RGB", (1000, 1000), color="red")
        img.save(self.large_image_path)
        
        # Create a test low-res image (100x100)
        self.small_image_path = os.path.join(CACHE_DIR, "test_small.png")
        img_small = Image.new("RGB", (100, 100), color="blue")
        img_small.save(self.small_image_path)

    def tearDown(self):
        # Clean up files created
        for p in [self.large_image_path, self.small_image_path]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

    def test_no_optimization_needed_for_small_images(self):
        # Small image (100x100) with max_dim=500 should return the original path directly
        res = get_or_create_optimized_image(self.small_image_path, max_dim=500)
        self.assertEqual(res, os.path.abspath(self.small_image_path))

    def test_optimization_downscales_large_images(self):
        # Large image (1000x1000) with max_dim=500 should return a cached optimized image path
        res = get_or_create_optimized_image(self.large_image_path, max_dim=500)
        self.assertNotEqual(res, os.path.abspath(self.large_image_path))
        self.assertTrue(os.path.exists(res))
        
        # Verify optimized image size is indeed downscaled
        with Image.open(res) as img:
            w, h = img.size
            self.assertEqual(w, 500)
            self.assertEqual(h, 500)

        # Re-running optimization should hit the cache
        res_cached = get_or_create_optimized_image(self.large_image_path, max_dim=500)
        self.assertEqual(res_cached, res)

    @patch("requests.get")
    def test_download_and_optimize_remote_image(self, mock_get):
        # Mock requests.get to return a valid response containing small image bytes
        mock_response = MagicMock()
        mock_response.status_code = 200
        
        # Write small image to bytes
        import io
        img_bytes = io.BytesIO()
        Image.new("RGB", (120, 120), color="green").save(img_bytes, format="PNG")
        mock_response.content = img_bytes.getvalue()
        
        mock_get.return_value = mock_response

        # Test download
        url = "https://example.com/avatar_test.png"
        res = get_or_create_optimized_image(url, max_dim=500)
        
        # It should download it, determine it's <= 500px, and return the downloaded file path
        self.assertTrue(res.startswith(DOWNLOAD_DIR))
        self.assertTrue(os.path.exists(res))
        with Image.open(res) as img:
            w, h = img.size
            self.assertEqual(w, 120)
            self.assertEqual(h, 120)

    @patch("requests.get")
    def test_failed_download_falls_back_to_url(self, mock_get):
        mock_get.side_effect = Exception("Network down")
        url = "https://example.com/failed_test.png"
        res = get_or_create_optimized_image(url, max_dim=500)
        self.assertEqual(res, url)


if __name__ == "__main__":
    unittest.main()
