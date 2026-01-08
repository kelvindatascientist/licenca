import streamlit_authenticator as stauth
import sys

# How to use:
# Run this script with the passwords you want to hash as arguments.
# Example: python generate_keys.py mypassword123 anotherpassword456

def generate_hashes(passwords):
    print("\n🔐 Generating Password Hashes\n" + "="*30)
    
    for password in passwords:
        try:
            # Generate hash using streamlit-authenticator
            hashed = stauth.Hasher().hash(password)
            print(f"Password: {password}")
            print(f"Hash:     {hashed}")
            print("-" * 30)
        except Exception as e:
            print(f"Error hashing '{password}': {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        passwords_to_hash = sys.argv[1:]
    else:
        # Default if no arguments provided
        print("No passwords provided. Using default '123456' for demonstration.")
        passwords_to_hash = ['123456']
    
    generate_hashes(passwords_to_hash)
    print("\n📋 Copy the hash above and paste it into your config.yaml file under 'password'.")
