# This is the upload_image method to be added to the official DeSo Python SDK
# It should be inserted into the DeSoDexClient class

def upload_image(self, image_path: str, extra_headers: Optional[Dict[str, str]] = None) -> str:
    """
    Upload an image to DeSo and return the image URL.

    Args:
        image_path (str): Path to the image file to upload.
        extra_headers (Optional[Dict[str, str]]): Additional headers for the HTTP request.

    Returns:
        str: The URL where the uploaded image can be accessed.

    Raises:
        requests.exceptions.RequestException: If the upload request fails.
        json.JSONDecodeError: If the response parsing fails.
        ValueError: If the server returns a non-200 status code or ImageURL not found.
        FileNotFoundError: If the image file doesn't exist.
    """
    url = f"{self.node_url}/api/v0/upload-image"
    
    try:
        with open(image_path, 'rb') as image_file:
            files = {'file': image_file}
            headers = {'Origin': self.node_url}
            
            if extra_headers:
                headers.update(extra_headers)
            
            response = requests.post(url, files=files, headers=headers)
            
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                try:
                    error_json = response.json()
                except ValueError:
                    error_json = response.text
                raise requests.exceptions.HTTPError(f"HTTP Error: {e}, Response: {error_json}")
            
            try:
                response_data = response.json()
            except json.JSONDecodeError as e:
                raise json.JSONDecodeError(f"Error parsing upload response: {str(e)}")
            
            image_url = response_data.get('ImageURL')
            if not image_url:
                raise ValueError("ImageURL not found in response")
            
            return image_url
            
    except FileNotFoundError:
        raise FileNotFoundError(f"Image file not found: {image_path}")
    except requests.exceptions.RequestException as e:
        raise requests.exceptions.RequestException(f"Upload request failed: {str(e)}")
