# Email Reporting Setup

This guide explains how to set up daily email reports for the IQ-720 Trading Bot.

## Overview

The trading bot now includes functionality to send daily reports via email at 6:00 AM South Africa Time (SAT). These reports include:

- Trading performance summary
- Performance metrics per currency pair
- Market conditions and optimal pairs for the day

## Email Configuration

To enable email reporting, you need to provide SMTP credentials. For Gmail, you'll need to use an App Password instead of your regular password.

### Setting Up Gmail App Password

1. Go to your Google Account settings
2. Navigate to Security → 2-Step Verification
3. At the bottom, click on "App passwords"
4. Select "Mail" as the app and "Other" as the device
5. Enter "IQ-720 Trading Bot" as the name
6. Copy the generated 16-character password

### Configuration Steps

1. Copy the example configuration file:
   ```bash
   cp email_config.env.example .env
   ```

2. Edit the `.env` file with your email credentials:
   ```
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USERNAME=your-email@gmail.com
   SMTP_PASSWORD=your-app-password-here
   EMAIL_RECIPIENTS=["aurevian22@gmail.com", "galdiale@gmail.com"]
   DAILY_REPORT_TIME=06:00
   ```

3. When deploying to the server using `update_bot.sh`, the script will automatically update the email configuration on the server.

## Customizing Report Recipients

To change the email recipients, update the `EMAIL_RECIPIENTS` field in the `.env` file. Use JSON array format with email addresses in quotes.

Example:
```
EMAIL_RECIPIENTS=["email1@example.com", "email2@example.com"]
```

## Customizing Report Time

To change the time when reports are sent, update the `DAILY_REPORT_TIME` field in the `.env` file. Use 24-hour format (HH:MM) in South Africa Time (SAT).

Example for 8:30 AM SAT:
```
DAILY_REPORT_TIME=08:30
```

## Testing Email Configuration

To test if your email configuration is working correctly, you can run:

```bash
python -c "from src.utils.email_notifier import email_notifier; email_notifier.send_email('Test Email', 'This is a test email from IQ-720 Trading Bot')"
```

If successful, both email addresses (aurevian22@gmail.com and galdiale@gmail.com) should receive a test email.

## Troubleshooting

If emails are not being sent:

1. Check the logs for error messages related to email sending
2. Verify that the SMTP credentials are correct
3. If using Gmail, ensure that you're using an App Password and not your regular password
4. Check if your email provider has any restrictions on sending emails through SMTP
