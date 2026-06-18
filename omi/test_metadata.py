import requests
import sys

# Define your Page Access Token
PAGE_ACCESS_TOKEN = "EAAUwelxKXkABRjz7688ABSfv5oEd27TJ7zxohKTaDdsyTuv1zLE5dWRgulCEZCsUZCh0cCZC3L72zqbXEk1ntvPYZBE0KpagETZCNHxsz0ZAlJfmr7RSuBiZCpOm0Tgu6V51toGPV7q2H07AzTtf1b4HpJ2ZBLnybqKl1isnEmgMqf8S3jSTTLwLpJtTzYETKwKg5H17QD4ZAzrhMsZABSCv0kbZCXT4gZDZD"
API_VERSION = "v25.0"

def get_page_metadata():
    print("--- Fetching Page Info ---")
    url = f"https://graph.facebook.com/{API_VERSION}/me"
    params = {
        "fields": "id,name,category,link",
        "access_token": PAGE_ACCESS_TOKEN
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.ok:
            data = response.json()
            print(f"Page Name:     {data.get('name')}")
            print(f"Page ID:       {data.get('id')}")
            print(f"Category:      {data.get('category')}")
            print(f"Facebook Link: {data.get('link')}")
            return data.get('id')
        else:
            print(f"Error fetching page info: HTTP {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Request failed: {e}")
    return None

def get_subscribed_webhooks():
    print("\n--- Fetching Subscribed Webhook Apps ---")
    url = f"https://graph.facebook.com/{API_VERSION}/me/subscribed_apps"
    params = {
        "access_token": PAGE_ACCESS_TOKEN
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.ok:
            data = response.json().get('data', [])
            if not data:
                print("No apps are currently subscribed to this Page's webhooks.")
            for app in data:
                print(f"App Name:           {app.get('name')}")
                print(f"App ID:             {app.get('id')}")
                print(f"Subscribed Fields:  {app.get('subscribed_fields')}")
        else:
            print(f"Error fetching subscriptions: HTTP {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Request failed: {e}")

def test_user_profile_access(psid):
    print(f"\n--- Testing Profile Resolution for PSID: {psid} ---")
    url = f"https://graph.facebook.com/{API_VERSION}/{psid}"
    params = {
        "fields": "name,first_name,last_name,profile_pic",
        "access_token": PAGE_ACCESS_TOKEN
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        if response.ok:
            data = response.json()
            print("Successfully resolved profile:")
            print(f"Full Name:   {data.get('name')}")
            print(f"First Name:  {data.get('first_name')}")
            print(f"Last Name:   {data.get('last_name')}")
            print(f"Profile Pic: {data.get('profile_pic')}")
        else:
            print(f"Failed to resolve profile: HTTP {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    page_id = get_page_metadata()
    if page_id:
        get_subscribed_webhooks()
        
        # If a PSID is provided as a command line argument, test profile resolution
        if len(sys.argv) > 1:
            test_user_profile_access(sys.argv[1])
        else:
            print("\nTo test profile name resolution for a user, run: python test_metadata.py <PSID>")
