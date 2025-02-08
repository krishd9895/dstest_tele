import requests
import easyocr
import os
from PIL import Image
from io import BytesIO
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
import time
from session_manager(headless) import session_manager
import json

# Bot instance handling
bot_instances = {}
chat_ids = {}
user_inputs = {}
last_message_id = {}
status_logs = {}


def set_bot_instance(bot, chat_id):
    global bot_instances, chat_ids
    bot_instances[chat_id] = bot
    chat_ids[chat_id] = chat_id


def bot_log(message, user_id=None):
    if user_id in bot_instances and user_id in chat_ids:
        try:
            # Delete previous message if exists
            if user_id in last_message_id:
                try:
                    bot_instances[user_id].delete_message(chat_ids[user_id], last_message_id[user_id])
                except:
                    pass  # Ignore if message already deleted

            # Send new message and store its ID
            msg = bot_instances[user_id].send_message(chat_ids[user_id], str(message))
            last_message_id[user_id] = msg.message_id
        except Exception as e:
            print(f"Failed to send message to bot: {e}")
            print(message)
    else:
        print(message)


def clear_status(user_id):
    """Clear the status message for a user"""
    if user_id in last_message_id:
        try:
            bot_instances[user_id].delete_message(chat_ids[user_id], last_message_id[user_id])
        except:
            pass  # Ignore if message already deleted
        del last_message_id[user_id]


def bot_send_image(image_path, caption, user_id):
    if user_id in bot_instances and user_id in chat_ids:
        try:
            with open(image_path, 'rb') as photo:
                bot_instances[user_id].send_photo(chat_ids[user_id], photo, caption=caption)
        except Exception as e:
            print(f"Failed to send image to bot: {e}")
    else:
        print(f"Would send image: {image_path} with caption: {caption}")


def bot_input(prompt, user_id=None):
    if user_id in bot_instances and user_id in chat_ids:
        bot_instances[user_id].send_message(chat_ids[user_id], prompt)
        # Set the user as waiting for input
        user_inputs[user_id] = None
        # Wait for input (with timeout)
        timeout = 60  # 60 seconds timeout
        start_time = time.time()
        while user_inputs[user_id] is None:
            if time.time() - start_time > timeout:
                bot_log("⚠️ Input timeout. Please try again.", user_id)
                return None
            time.sleep(0.5)
        response = user_inputs[user_id]
        user_inputs[user_id] = None
        return response
    return input(prompt)


# --------------------------
# CONFIGURATION
# --------------------------
website_url = os.getenv('URL')
max_retries = 3

# XPaths (Pre-Login)
XPATHS = {
    "username": "/html/body/form/div[9]/div/div[2]/div/div/div[2]/div/div[2]/div/input",
    "password": "/html/body/form/div[9]/div/div[2]/div/div/div[2]/div/div[2]/div[2]/input",
    "captcha_img": "/html/body/form/div[9]/div/div[2]/div/div/div[2]/div/div[2]/div[3]/div/img",
    "captcha_input": "/html/body/form/div[9]/div/div[2]/div/div/div[2]/div/div[2]/div[4]/input",
    "login_button": "/html/body/form/div[9]/div/div[2]/div/div/div[2]/div/div[2]/input",
    "login_failure": "/html/body/div[2]/h2",
    "login_success": [
        "/html/body/form/header/nav/div/div/div/div/div/ul/li/a/span",
        "/html/body/form/header/nav/div/div/div/div/div/ul/li/a"
    ]
}

# XPaths (Post-Login)
POST_LOGIN_XPATHS = {
    "Page1_btn_path": "/html/body/form/div[4]/div/div/div/div/div/div/input",
    "Page2_verify_path": "/html/body/form/div[4]/div/div/div/div/div/div/span",
    "Page2_btn_path": "/html/body/form/div[4]/div/div/div/div/div/div[2]/div[2]/div/div/div/div/ul/input",
    "Page3_btn_path": "/html/body/form/header/nav/div/div/ul/li[2]/a"
}

# Initialize components
reader = easyocr.Reader(["en"])


# --------------------------
# LOGIN FUNCTIONS
# --------------------------
def load_credentials(user_id):
    """Load credentials from JSON file"""
    try:
        with open('credentials.json', 'r') as f:
            credentials = json.load(f)
            return credentials.get(str(user_id))
    except FileNotFoundError:
        with open('credentials.json', 'w') as f:
            json.dump({}, f)
        return None
    except json.JSONDecodeError:
        return None


def save_credentials(user_id, username, password):
    """Save credentials to JSON file"""
    try:
        with open('credentials.json', 'r') as f:
            credentials = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        credentials = {}

    credentials[str(user_id)] = {
        'username': username,
        'password': password
    }

    with open('credentials.json', 'w') as f:
        json.dump(credentials, f, indent=4)


def get_user_credentials(user_id):
    """Get or request user credentials"""
    credentials = load_credentials(user_id)

    if credentials:
        return credentials['username'], credentials['password']

    bot_log("⚠️ No saved credentials found. Please provide your login details.", user_id)

    # Ask for username
    bot_log("📝 Please enter your username:", user_id)
    username = bot_input("Enter username:", user_id)
    if not username:
        bot_log("❌ Username cannot be empty", user_id)
        return None, None

    # Ask for password
    bot_log("🔑 Please enter your password:", user_id)
    password = bot_input("Enter password:", user_id)
    if not password:
        bot_log("❌ Password cannot be empty", user_id)
        return None, None

    return username, password


def handle_login_attempt(user_id):
    """Main login handler with automatic retries and manual fallback"""
    clear_status(user_id)  # Clear previous status
    session = session_manager.get_session(user_id)
    driver = session['driver']
    success = False

    # Get credentials
    username, password = get_user_credentials(user_id)
    if not username or not password:
        bot_log("❌ Login failed: Invalid credentials", user_id)
        return False

    bot_log("\n" + "=" * 40, user_id)
    bot_log("ATTEMPTING LOGIN".center(40), user_id)
    bot_log("=" * 40, user_id)

    # Try automatic login first
    success = automatic_login(driver, username, password, user_id)
    if success:
        save_credentials(user_id, username, password)
        return True

    # Before trying manual mode, check if credentials are valid
    driver.get(website_url)
    time.sleep(2)
    enter_credentials(driver, username, password, user_id)
    submit_login(driver, user_id)

    try:
        error_element = driver.find_elements(By.XPATH, XPATHS["login_failure"])
        if error_element:
            error_text = error_element[0].text.strip()
            if "invalid" in error_text.lower() or "incorrect" in error_text.lower():
                bot_log("❌ Login Failed: Invalid credentials. Please try again with correct username and password.",
                        user_id)
                return False
    except Exception:
        pass

    # Only proceed to manual mode if credentials weren't wrong
    bot_log("\n" + "=" * 40, user_id)
    bot_log("SWITCHING TO MANUAL MODE".center(40), user_id)
    bot_log("=" * 40, user_id)
    success = manual_login(driver, username, password, user_id)
    if success:
        save_credentials(user_id, username, password)
    return success


def automatic_login(driver, username, password, user_id):
    """Automatic login attempts with OCR"""
    bot_log(f"\n🌀 Attempting automatic login", user_id)
    driver.get(website_url)
    time.sleep(2)

    if not enter_credentials(driver, username, password, user_id):
        return False

    captcha_text = process_captcha(driver, user_id)
    if not captcha_text:
        return False

    submit_login(driver, user_id)

    # Check login result
    try:
        error_element = driver.find_elements(By.XPATH, XPATHS["login_failure"])
        if error_element:
            error_text = error_element[0].text.strip()
            if "invalid" in error_text.lower() or "incorrect" in error_text.lower():
                bot_log("❌ Login Failed: Invalid credentials. Please try again with correct username and password.",
                        user_id)
                # Clear saved credentials since they're wrong
                if os.path.exists('credentials.json'):
                    credentials = json.load(open('credentials.json', 'r'))
                    if str(user_id) in credentials:
                        del credentials[str(user_id)]
                        json.dump(credentials, open('credentials.json', 'w'), indent=4)
                return False
    except Exception:
        pass

    if check_login_result(driver, user_id):
        bot_log("🎉 AUTOMATIC LOGIN SUCCESSFUL!, now try /operations", user_id)
        return True

    return False


def manual_login(driver, username, password, user_id):
    """Manual login handler"""
    bot_log("\n📝 Starting manual login process...", user_id)
    driver.get(website_url)
    time.sleep(2)

    if not enter_credentials(driver, username, password, user_id):
        return False

    captcha_text = process_captcha_manual(driver, user_id)
    if not captcha_text:
        return False

    submit_login(driver, user_id)

    # Check for invalid credentials before proceeding
    try:
        error_element = driver.find_elements(By.XPATH, XPATHS["login_failure"])
        if error_element:
            error_text = error_element[0].text.strip()
            if "invalid" in error_text.lower() or "incorrect" in error_text.lower():
                bot_log("❌ Login Failed: Invalid credentials. Please try again with correct username and password.",
                        user_id)
                # Clear saved credentials since they're wrong
                if os.path.exists('credentials.json'):
                    credentials = json.load(open('credentials.json', 'r'))
                    if str(user_id) in credentials:
                        del credentials[str(user_id)]
                        json.dump(credentials, open('credentials.json', 'w'), indent=4)
                return False
    except Exception:
        pass

    if check_login_result(driver, user_id):
        bot_log("🎉 MANUAL LOGIN SUCCESSFUL!,now try /operations", user_id)
        return True

    return False


# --------------------------
# LOGIN HELPER FUNCTIONS
# --------------------------
def enter_credentials(driver, username, password, user_id):
    """Enter username and password"""
    try:
        driver.find_element(By.XPATH, XPATHS["username"]).send_keys(username)
        driver.find_element(By.XPATH, XPATHS["password"]).send_keys(password)
        bot_log("✅ Credentials entered", user_id)
        return True
    except Exception as e:
        bot_log(f"❌ Error entering credentials: {str(e)}", user_id)
        return False


def process_captcha(driver, user_id):
    """Automatic captcha processing"""
    try:
        captcha_element = driver.find_element(By.XPATH, XPATHS["captcha_img"])
        captcha_url = captcha_element.get_attribute("src")
        response = requests.get(captcha_url)
        Image.open(BytesIO(response.content)).save("captcha_auto.png")

        result = reader.readtext("captcha_auto.png")
        captcha_text = result[0][1].replace(" ", "").strip() if result else ""
        bot_log(f"🔍 Recognized Captcha: {captcha_text}", user_id)

        driver.find_element(By.XPATH, XPATHS["captcha_input"]).send_keys(captcha_text)
        return captcha_text
    except Exception as e:
        bot_log(f"❌ Captcha processing failed: {str(e)}", user_id)
        return None


def process_captcha_manual(driver, user_id):
    """Manual captcha handling"""
    try:
        # Get and save captcha
        captcha_element = driver.find_element(By.XPATH, XPATHS["captcha_img"])
        captcha_url = captcha_element.get_attribute("src")
        response = requests.get(captcha_url)
        captcha_path = "captcha_manual.png"
        Image.open(BytesIO(response.content)).save(captcha_path)

        # Send captcha image to bot
        bot_send_image(captcha_path, "📝 Please enter the captcha text:", user_id)

        # Get captcha text from user
        captcha_text = bot_input("Type the captcha text shown in the image above:", user_id)
        if captcha_text:
            driver.find_element(By.XPATH, XPATHS["captcha_input"]).send_keys(captcha_text)
            return captcha_text
        return None
    except Exception as e:
        bot_log(f"❌ Manual captcha failed: {str(e)}", user_id)
        return None


def submit_login(driver, user_id):
    """Click login button"""
    try:
        driver.find_element(By.XPATH, XPATHS["login_button"]).click()
        bot_log("🔄 Submitting login...", user_id)
        time.sleep(5)
    except Exception as e:
        bot_log(f"❌ Login submission failed: {str(e)}", user_id)


def check_login_result(driver, user_id):
    """Check login success/failure with simple text content logging"""
    try:
        error_element = driver.find_elements(By.XPATH, XPATHS["login_failure"])
        if error_element:
            error_text = error_element[0].text.strip()
            bot_log(f"❌ Login Failed: {error_text}", user_id)
            return False

        bot_log("\nChecking success elements:", user_id)
        for path in XPATHS["login_success"]:
            elements = driver.find_elements(By.XPATH, path)
            if elements:
                bot_log(f"✅ Found: {elements[0].text.strip()}", user_id)
                return True
            else:
                bot_log(f"❌ Element not found", user_id)

        bot_log("⚠️ Unknown login status - no success elements found", user_id)
        return False
    except Exception as e:
        bot_log(f"❌ Login check failed: {str(e)}", user_id)
        return False


# --------------------------
# POST-LOGIN OPERATIONS
# --------------------------
def post_login_click_button(driver, button_element, user_id):
    """
    Attempts to click a button using multiple methods
    """
    button_text = button_element.text.strip() or button_element.get_attribute('value')

    try:
        driver.execute_script("arguments[0].click();", button_element)
        bot_log(f"✅ Clicked '{button_text}' using JavaScript", user_id)
        return True
    except Exception as e:
        bot_log(f"❌ JavaScript click failed for '{button_text}': {str(e)}", user_id)

    try:
        from selenium.webdriver.common.action_chains import ActionChains
        actions = ActionChains(driver)
        actions.move_to_element(button_element).click().perform()
        bot_log(f"✅ Clicked '{button_text}' using Action Chains", user_id)
        return True
    except Exception as e:
        bot_log(f"❌ Action Chains click failed for '{button_text}': {str(e)}", user_id)

    try:
        driver.execute_script("""
            arguments[0].style.opacity = '1'; 
            arguments[0].style.display = 'block';
            arguments[0].style.visibility = 'visible';
        """, button_element)
        button_element.click()
        bot_log(f"✅ Clicked '{button_text}' after forcing visibility", user_id)
        return True
    except Exception as e:
        bot_log(f"❌ Forced visibility click failed for '{button_text}': {str(e)}", user_id)

    return False


def extract_form_data(driver, user_id):
    """
    Extracts and prints relevant information from the data entry form dynamically.

    """
    try:
        bot_log("\n" + "=" * 40, user_id)
        bot_log("FORM INFORMATION".center(40), user_id)
        bot_log("=" * 40, user_id)

        bot_log("\n📝 Form Data:", user_id)

        input_elements = driver.find_elements(By.TAG_NAME, "input")

        for element in input_elements:
            field_id = element.get_attribute('id')
            value = element.get_attribute('value')
            readonly = element.get_attribute('readonly')
            label_elements = driver.find_elements(By.XPATH, f"//label[@for='{field_id}']")
            label = label_elements[0].text if label_elements else field_id

            if any(substring in field_id.lower() for substring in
                   ["event", "viewstate", "scroll", "validation", "clientstate", "hidden", "logout", "pwchange"]):
                continue

            label = label.replace("HomeContentPlaceHolder_txt", "")

            status = "🔒" if readonly else "✏️"
            bot_log(f"{status} {label}: {value}", user_id)

    except Exception as e:
        bot_log(f"❌ Error extracting form information: {str(e)}", user_id)


def post_login_operations(user_id):
    """Execute actions after successful login"""
    clear_status(user_id)  # Clear previous status
    session = session_manager.get_session(user_id)
    driver = session['driver']
    bot_log("\n" + "=" * 40, user_id)
    bot_log("POST-LOGIN OPERATIONS".center(40), user_id)
    bot_log("=" * 40, user_id)

    try:
        for file in ["captcha_auto.png", "captcha_manual.png"]:
            if os.path.exists(file):
                os.remove(file)

        Page1_btn = driver.find_element(By.XPATH, POST_LOGIN_XPATHS["Page1_btn_path"])
        button_text = Page1_btn.text.strip() or Page1_btn.get_attribute('value')
        bot_log(f"🖱️ Found button: {button_text}", user_id)
        if not post_login_click_button(driver, Page1_btn, user_id):
            raise Exception(f"Failed to click '{button_text}' button")
        time.sleep(2)

        Page2_verify = driver.find_element(By.XPATH, POST_LOGIN_XPATHS["Page2_verify_path"])
        bot_log(f"📋 Found section: {Page2_verify.text}", user_id)

        Page2_btn = driver.find_element(By.XPATH, POST_LOGIN_XPATHS["Page2_btn_path"])
        button_text = Page2_btn.text.strip() or Page2_btn.get_attribute('value')
        bot_log(f"🖱️ Found button: {button_text}", user_id)
        if not post_login_click_button(driver, Page2_btn, user_id):
            raise Exception(f"Failed to click '{button_text}' button")
        time.sleep(2)

        Page3_btn = driver.find_element(By.XPATH, POST_LOGIN_XPATHS["Page3_btn_path"])
        button_text = Page3_btn.text.strip() or Page3_btn.get_attribute('value')
        bot_log(f"🖱️ Found button: {button_text}", user_id)
        if not post_login_click_button(driver, Page3_btn, user_id):
            raise Exception(f"Failed to click '{button_text}' button")
        time.sleep(2)

        extract_form_data(driver, user_id)

        try:
            input_element = driver.find_element(By.XPATH,
                                                "/html/body/form/div[4]/div/div/div/div/div/div/div[2]/div/div/div[15]/input")
            bot_log("💬 Please enter a value for the input field:", user_id)
            user_value = bot_input("Enter your value:", user_id)
            if user_value:
                input_element.clear()
                input_element.send_keys(user_value)
                bot_log("✅ Value entered successfully!", user_id)
                time.sleep(2)
        except NoSuchElementException:
            bot_log("⚠️ Input field not found. Data might have been saved earlier.", user_id)
            return True
        except Exception as e:
            bot_log(f"⚠️ Error while entering value: {str(e)}", user_id)
            return False

        try:
            save_button = driver.find_element(By.XPATH,
                                              "/html/body/form/div[4]/div/div/div/div/div/div/div[2]/div/div/div[19]/input")
            save_button.click()
            bot_log("✅ Save button clicked successfully!", user_id)
            return True
        except NoSuchElementException:
            bot_log("ℹ️ Unable to find save button. The data might have been saved earlier.", user_id)
            return True
        except Exception as e:
            bot_log(f"❌ Error while saving: {str(e)}", user_id)
            return False

    except Exception as e:
        bot_log(f"ℹ️ Unable to complete all operations. The data might have been saved earlier.", user_id)
        return False


# --------------------------
# MAIN EXECUTION
# --------------------------
def main(user_id):
    try:
        if handle_login_attempt(user_id):
            post_login_operations(user_id)
        else:
            bot_log("\n❌ All login attempts failed", user_id)

    finally:
        bot_input("\nPress Enter to close browser...", user_id)
        session = session_manager.get_session(user_id)
        session['driver'].quit()
        bot_log("Browser closed", user_id)


if __name__ == "__main__":
    main("user_id")
