# Utility functions for the Parental Monitor application
# For now, this will primarily house encryption/decryption logic.

from cryptography.fernet import Fernet
import os

# This global key and cipher_suite might be better managed within a class
# or passed around, but for simplicity in utils used by logger directly:
_ENCRYPTION_KEY_BYTES = None
_CIPHER_SUITE = None

def generate_key_to_file(key_path):
    """Generates a new Fernet key and saves it to the specified path."""
    key = Fernet.generate_key()
    os.makedirs(os.path.dirname(key_path), exist_ok=True)
    with open(key_path, 'wb') as key_file:
        key_file.write(key)
    if os.name == 'posix':
        try:
            os.chmod(key_path, 0o600) # Read/write for owner only
        except Exception as e:
            # Log this failure if a logger is available and configured
            print(f"Warning: Failed to set permissions on key file {key_path}: {e}")
    print(f"Generated new encryption key at {key_path}")
    return key

def load_key_from_file(key_path):
    """Loads a Fernet key from the specified path."""
    if not os.path.exists(key_path):
        return None
    with open(key_path, 'rb') as key_file:
        key = key_file.read()
    return key

def initialize_encryption(key_path):
    """
    Initializes the encryption utility.
    Loads key from key_path, or generates a new one if not found.
    Sets up the global _CIPHER_SUITE for use by encrypt/decrypt functions.
    """
    global _ENCRYPTION_KEY_BYTES, _CIPHER_SUITE

    _ENCRYPTION_KEY_BYTES = load_key_from_file(key_path)

    if _ENCRYPTION_KEY_BYTES is None:
        print(f"Encryption key not found at {key_path}. Generating a new one.")
        _ENCRYPTION_KEY_BYTES = generate_key_to_file(key_path)
        if not _ENCRYPTION_KEY_BYTES: # Should not happen if generate_key_to_file is robust
             raise RuntimeError(f"Failed to generate and save encryption key to {key_path}")

    try:
        _CIPHER_SUITE = Fernet(_ENCRYPTION_KEY_BYTES)
        print(f"Encryption initialized successfully using key from {key_path}.")
    except Exception as e:
        # This could happen if the key file is corrupted or not a valid Fernet key
        _CIPHER_SUITE = None # Ensure it's None if init fails
        # Potentially log this error using the main app logger if available and initialized
        # For now, print and raise, as this is critical.
        print(f"CRITICAL: Failed to initialize Fernet cipher with key from {key_path}. Error: {e}")
        # Consider renaming corrupted key and generating a new one, or halting.
        # For MVP, halting might be safer if key is compromised/corrupt.
        raise ValueError(f"Invalid or corrupted encryption key at {key_path}. Cannot proceed.") from e


def get_cipher():
    """
    Returns the initialized Fernet cipher suite.
    Raises RuntimeError if encryption has not been initialized.
    """
    if _CIPHER_SUITE is None:
        # This implies initialize_encryption was not called or failed.
        # The logger module calls initialize_encryption (which calls initialize_encryption from here).
        # If direct use of utils.encrypt/decrypt is made before logger init, this could be an issue.
        raise RuntimeError("Encryption has not been initialized. Call utils.initialize_encryption(key_path) first.")
    return _CIPHER_SUITE

def encrypt(data_bytes):
    """Encrypts data_bytes using the initialized cipher."""
    cipher = get_cipher()
    return cipher.encrypt(data_bytes)

def decrypt(token_bytes):
    """Decrypts token_bytes using the initialized cipher."""
    cipher = get_cipher()
    try:
        return cipher.decrypt(token_bytes)
    except Exception as e: # Catching generic Exception, Fernet raises InvalidToken for most issues
        # print(f"Decryption failed: {e}") # Log this if necessary
        # This might be common if trying to decrypt non-encrypted or corrupted data
        raise # Re-raise the original Fernet exception (e.g., InvalidToken)

# --- Example Usage and Test ---
if __name__ == '__main__':
    print("Encryption Utilities Test")

    test_key_file = "test_utils_encryption.key"

    # Clean up old key file if it exists
    if os.path.exists(test_key_file):
        os.remove(test_key_file)

    # 1. Initialize (should generate a key)
    print(f"\n1. Initializing encryption (key file: {test_key_file})...")
    try:
        initialize_encryption(test_key_file)
        print("Initialization successful.")
    except Exception as e:
        print(f"Error during initial initialization: {e}")
        exit(1)

    assert os.path.exists(test_key_file), "Key file was not created."

    # 2. Encrypt some data
    print("\n2. Encrypting data...")
    original_data = b"This is some secret data for testing encryption!"
    print(f"Original: {original_data.decode()}")

    try:
        encrypted_data = encrypt(original_data)
        print(f"Encrypted: {encrypted_data[:30]}... (truncated)") # Show only part of it
        assert original_data != encrypted_data, "Encryption did not change data."
    except Exception as e:
        print(f"Error during encryption: {e}")
        exit(1)

    # 3. Decrypt the data
    print("\n3. Decrypting data...")
    try:
        decrypted_data = decrypt(encrypted_data)
        print(f"Decrypted: {decrypted_data.decode()}")
        assert original_data == decrypted_data, "Decryption did not match original."
        print("Encryption and decryption successful!")
    except Exception as e:
        print(f"Error during decryption: {e}")
        exit(1)

    # 4. Test re-initialization (should load existing key)
    print(f"\n4. Re-initializing encryption (should load existing key from {test_key_file})...")
    _CIPHER_SUITE = None # Reset to simulate fresh start
    try:
        initialize_encryption(test_key_file) # Should load the key created earlier
        print("Re-initialization successful.")
    except Exception as e:
        print(f"Error during re-initialization: {e}")
        exit(1)

    # 5. Decrypt again with re-initialized cipher
    print("\n5. Decrypting data again with re-initialized cipher...")
    try:
        decrypted_data_again = decrypt(encrypted_data)
        print(f"Decrypted: {decrypted_data_again.decode()}")
        assert original_data == decrypted_data_again, "Decryption after re-init failed."
        print("Decryption after re-initialization successful!")
    except Exception as e:
        print(f"Error during decryption after re-init: {e}")
        exit(1)

    # 6. Test decryption of invalid token
    print("\n6. Testing decryption of an invalid token...")
    invalid_token = b"thisisnotavalidfernettoken"
    try:
        decrypt(invalid_token)
        print("FAIL: Decryption of invalid token did not raise an error.")
    except from cryptography.fernet import InvalidToken:
        print("SUCCESS: Decryption of invalid token correctly raised InvalidToken.")
    except Exception as e:
        print(f"FAIL: Decryption of invalid token raised an unexpected error: {e}")

    # Clean up the test key file
    if os.path.exists(test_key_file):
        os.remove(test_key_file)
    print(f"\nTest finished. Cleaned up {test_key_file}.")
