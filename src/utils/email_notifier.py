"""
Email notification module for the trading bot.
Sends reports and alerts via email.
"""
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
import logging
from typing import List, Dict, Optional, Any
import json

class EmailNotifier:
    """
    Handles email notifications for the trading bot.
    """
    
    def __init__(self, smtp_server: str = "smtp.gmail.com", 
                 smtp_port: int = 587,
                 smtp_username: Optional[str] = None,
                 smtp_password: Optional[str] = None):
        """
        Initialize the email notifier.
        
        Args:
            smtp_server: SMTP server address
            smtp_port: SMTP server port
            smtp_username: SMTP username (email address)
            smtp_password: SMTP password or app password
        """
        self.logger = logging.getLogger(__name__)
        
        # SMTP settings
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username or os.environ.get('SMTP_USERNAME')
        self.smtp_password = smtp_password or os.environ.get('SMTP_PASSWORD')
        
        # Default recipients
        self.default_recipients = ["aurevian22@gmail.com", "galdiale@gmail.com"]
        
        if not self.smtp_username or not self.smtp_password:
            self.logger.warning("Email credentials not provided. Email notifications will not work.")
            
    def send_email(self, subject: str, body: str, recipients: Optional[List[str]] = None,
                  attachments: Optional[List[str]] = None, html: bool = False) -> bool:
        """
        Send an email.
        
        Args:
            subject: Email subject
            body: Email body content
            recipients: List of email addresses to send to (uses default if None)
            attachments: List of file paths to attach
            html: Whether body is HTML content
            
        Returns:
            True if email was sent successfully
        """
        if not self.smtp_username or not self.smtp_password:
            self.logger.error("Cannot send email: credentials not configured")
            return False
            
        # Use default recipients if none specified
        if not recipients:
            recipients = self.default_recipients
            
        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.smtp_username
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = subject
            
            # Add body
            if html:
                msg.attach(MIMEText(body, 'html'))
            else:
                msg.attach(MIMEText(body, 'plain'))
                
            # Add attachments
            if attachments:
                for file_path in attachments:
                    if not os.path.isfile(file_path):
                        self.logger.warning(f"Attachment not found: {file_path}")
                        continue
                        
                    with open(file_path, 'rb') as f:
                        attachment = MIMEApplication(f.read())
                        attachment.add_header(
                            'Content-Disposition', 
                            'attachment', 
                            filename=os.path.basename(file_path)
                        )
                        msg.attach(attachment)
                        
            # Connect to SMTP server and send
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
                
            self.logger.info(f"Email sent successfully to {', '.join(recipients)}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            return False
            
    def send_daily_report(self, report_data: Dict, 
                         performance_data: Optional[Dict] = None,
                         report_date: Optional[datetime] = None) -> bool:
        """
        Send a daily trading report.
        
        Args:
            report_data: Dictionary with report information
            performance_data: Dictionary with performance metrics
            report_date: Date of the report (uses today if None)
            
        Returns:
            True if email was sent successfully
        """
        # Use current date if none provided
        if not report_date:
            report_date = datetime.now()
            
        date_str = report_date.strftime("%Y-%m-%d")
        
        # Create subject
        subject = f"IQ-720 Trading Bot - Daily Report {date_str}"
        
        # Create email body
        body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                h1 {{ color: #2c3e50; }}
                h2 {{ color: #3498db; }}
                .stats {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0; }}
                .positive {{ color: green; }}
                .negative {{ color: red; }}
                table {{ border-collapse: collapse; width: 100%; margin: 15px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
            </style>
        </head>
        <body>
            <h1>IQ-720 Trading Bot - Daily Report</h1>
            <p>Date: {date_str}</p>
            
            <h2>Trading Summary</h2>
            <div class="stats">
        """
        
        # Add report data
        total_signals = report_data.get('total_signals', 0)
        total_trades = report_data.get('total_trades', 0)
        winning_trades = report_data.get('winning_trades', 0)
        win_rate = report_data.get('win_rate', 0) * 100
        
        body += f"""
                <p>Total Signals Generated: {total_signals}</p>
                <p>Total Trades Executed: {total_trades}</p>
                <p>Winning Trades: {winning_trades}</p>
                <p>Win Rate: <span class="{'positive' if win_rate >= 50 else 'negative'}">{win_rate:.2f}%</span></p>
            </div>
        """
        
        # Add performance data if available
        if performance_data:
            body += """
            <h2>Performance by Currency Pair</h2>
            <table>
                <tr>
                    <th>Pair</th>
                    <th>Trades</th>
                    <th>Win Rate</th>
                    <th>Profit Factor</th>
                    <th>Avg Profit</th>
                </tr>
            """
            
            # Add row for each pair
            for pair, stats in performance_data.items():
                pair_win_rate = stats.get('win_rate', 0) * 100
                profit_factor = stats.get('profit_factor', 0)
                avg_profit = stats.get('avg_profit', 0)
                total_pair_trades = stats.get('total_trades', 0)
                
                body += f"""
                <tr>
                    <td>{pair}</td>
                    <td>{total_pair_trades}</td>
                    <td class="{'positive' if pair_win_rate >= 50 else 'negative'}">{pair_win_rate:.2f}%</td>
                    <td>{profit_factor:.2f}</td>
                    <td class="{'positive' if avg_profit >= 0 else 'negative'}">{avg_profit:.2f}</td>
                </tr>
                """
                
            body += """
            </table>
            """
            
        # Add market outlook
        body += """
            <h2>Market Outlook</h2>
            <div class="stats">
        """
        
        # Add market conditions
        market_type = report_data.get('market_type', 'N/A')
        active_sessions = report_data.get('active_sessions', [])
        sessions_str = ', '.join(active_sessions) if active_sessions else 'No major session'
        optimal_pairs = report_data.get('optimal_pairs', [])
        optimal_pairs_str = ', '.join(optimal_pairs) if optimal_pairs else 'None'
        
        body += f"""
                <p>Market Type: {market_type}</p>
                <p>Active Sessions: {sessions_str}</p>
                <p>Optimal Pairs: {optimal_pairs_str}</p>
            </div>
        """
        
        # Close HTML
        body += """
            <p>This is an automated report from the IQ-720 Trading Bot.</p>
        </body>
        </html>
        """
        
        # Send email
        return self.send_email(subject, body, html=True)
        
    def send_signal_alert(self, signal_data: Dict) -> bool:
        """
        Send an email alert for a trading signal.
        
        Args:
            signal_data: Dictionary with signal information
            
        Returns:
            True if email was sent successfully
        """
        # Extract signal details
        direction = signal_data.get('direction', 'UNKNOWN')
        asset = signal_data.get('asset', 'UNKNOWN')
        strength = signal_data.get('strength_score', 0)
        rank = signal_data.get('rank', 0)
        
        # Create subject
        subject = f"IQ-720 Trading Bot - {direction} Signal for {asset} (Rank {rank})"
        
        # Create email body with HTML
        body = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                h1 {{ color: #2c3e50; }}
                .signal {{ padding: 15px; border-radius: 5px; margin: 10px 0; }}
                .BUY {{ background-color: rgba(46, 204, 113, 0.2); }}
                .SELL {{ background-color: rgba(231, 76, 60, 0.2); }}
                .indicators {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0; }}
                .strength {{ font-size: 24px; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>IQ-720 Trading Bot - Trading Signal</h1>
            
            <div class="signal {direction}">
                <h2>{direction} Signal - {asset}</h2>
                <p>Rank: #{rank}</p>
                <p>Strength: <span class="strength">{strength:.1f}/100</span></p>
                <p>Expiry: {signal_data.get('expiry_minutes', 1)} min</p>
                <p>Time: {signal_data.get('timestamp', datetime.now()).strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
            </div>
            
            <h2>Technical Indicators</h2>
            <div class="indicators">
        """
        
        # Add indicators
        indicators = signal_data.get('indicators', {})
        for name, value in indicators.items():
            if isinstance(value, (int, float)):
                body += f"<p>{name}: {value:.2f}</p>"
            else:
                body += f"<p>{name}: {value}</p>"
                
        # Add strength factors if available
        strength_factors = signal_data.get('strength_factors', {})
        if strength_factors:
            body += "<h2>Strength Factors</h2>"
            for factor, value in strength_factors.items():
                if isinstance(value, (int, float)):
                    body += f"<p>{factor}: {value:.2f}</p>"
                else:
                    body += f"<p>{factor}: {value}</p>"
                    
        # Add time context
        time_context = signal_data.get('time_context', '')
        if time_context:
            body += f"<h2>Market Context</h2><p>{time_context}</p>"
            
        # Close HTML
        body += """
            <p>This is an automated alert from the IQ-720 Trading Bot.</p>
        </body>
        </html>
        """
        
        # Send email
        return self.send_email(subject, body, html=True)

# Initialize email notifier
email_notifier = EmailNotifier()
