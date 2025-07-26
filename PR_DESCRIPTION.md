# Pull Request for DeSo Python SDK: Add Image Upload Functionality

## Description
This PR adds complete image upload functionality to the DeSo Python SDK, enabling developers to upload images directly to DeSo's media service and use them in posts.

## New Method: `upload_image`

### Overview
The `upload_image` method allows users to upload image files to DeSo and receive back the hosted URL that can be used in posts via the `image_urls` parameter.

### Method Signature
```python
def upload_image(self, image_path: str, user_public_key_base58check: str, extra_headers: Optional[Dict[str, str]] = None) -> str
```

### Parameters
- `image_path` (str): Path to the image file to upload
- `user_public_key_base58check` (str): Public key of the user uploading the image
- `extra_headers` (Optional[Dict[str, str]]): Additional headers for the HTTP request

### Returns
- `str`: The URL where the uploaded image can be accessed

### Raises
- `requests.exceptions.RequestException`: If the upload request fails
- `json.JSONDecodeError`: If the response parsing fails  
- `ValueError`: If the server returns a non-200 status code or ImageURL not found
- `FileNotFoundError`: If the image file doesn't exist

### Usage Example
```python
# Initialize client
client = DeSoDexClient(is_testnet=False, seed_phrase_or_hex=SEED_HEX)

# Upload an image
image_url = client.upload_image('path/to/image.png', PUBLIC_KEY)

# Use in a post
post_response = client.submit_post(
    updater_public_key_base58check=PUBLIC_KEY,
    body="Check out this chart!",
    image_urls=[image_url],  # Include uploaded image
    # ... other parameters
)
```

## Implementation Details

### API Endpoint
- Uses DeSo's `/api/v0/upload-image` endpoint
- Implements proper JWT authentication using ES256K algorithm
- Uses multipart/form-data with 'file' field name (matching DeSo frontend)
- Includes UserPublicKeyBase58Check parameter

### JWT Authentication
- **Fully Implemented**: Generates valid JWT tokens using user's private key
- **Algorithm**: ES256K (ECDSA with secp256k1 curve)
- **Signing**: Uses existing SDK crypto libraries (ecdsa, hashlib)
- **Format**: Standard JWT with header, payload, and signature

### Error Handling
- Comprehensive error handling for file operations
- Proper HTTP error response parsing
- Graceful handling of missing files and network errors
- Detailed error messages for debugging

### Integration
- Follows existing SDK patterns and conventions
- Compatible with existing `submit_post` method's `image_urls` parameter
- Maintains consistency with other SDK methods
- Uses SDK's existing key management and crypto libraries

## Use Cases
1. **Automated posting with charts/graphs**: Perfect for bots that generate data visualizations
2. **Image-rich social applications**: Apps that need to include user-generated images
3. **Content management tools**: Tools that upload and manage media content
4. **Analytics dashboards**: Systems that post performance charts and metrics

## Testing
The method has been implemented with:
- Proper JWT authentication and signing
- Integration with existing SDK crypto infrastructure
- Error scenarios (missing files, network errors, authentication failures)
- Compatible with DeSo's image upload API requirements

## Related
- Complements existing `submit_post` method
- Enables rich media posts on DeSo
- Follows DeSo's media upload API requirements
- Uses same authentication patterns as other SDK methods

## Files Changed
- `deso_sdk.py`: Added `upload_image` method to `DeSoDexClient` class
