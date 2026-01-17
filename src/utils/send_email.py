
import os
import logging
import sendgrid
from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType, Disposition
import base64

logger = logging.getLogger(__name__)

sg = sendgrid.SendGridAPIClient(api_key=os.environ.get('SENDGRID_API_KEY'))

async def send_email(recipient_email: str):
  """Send an email containing the property research results to the recipient."""
  # Create email with attachment
  from_email = Email("alukachiama@gmail.com")
  to_email = To(recipient_email)
  subject = f"Property Research Results"
  
  # Create the email content
  content = Content(
      "text/html",
      f"""
      <html>
      <body>
          <h2>Property Research Results</h2>
          <p>Please find attached the property research results for the addresses requested.</p>
          <p>The Excel file contains detailed information about property owners, contact details, and other relevant data.</p>
          <br>
          <p>Best regards,</p>
          <p>Property Research System</p>
      </body>
      </html>
      """
  )
  
  # Create the email
  message = Mail(
      from_email=from_email,
      to_emails=to_email,
      subject=subject,
      html_content=content
  )
  
  results_dir = os.path.join(os.getcwd(), "results")

  if results_dir:
    excel_path = os.path.join(results_dir, "property_owners.xlsx")
    
    # Create the attachment
    with open(excel_path, 'rb') as f:
        data = f.read()
        f.close()
    
    encoded = base64.b64encode(data).decode()
    attachment = Attachment()
    attachment.file_content = FileContent(encoded)
    attachment.file_type = FileType('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    attachment.file_name = FileName(os.path.basename(excel_path))
    attachment.disposition = Disposition('attachment')
    message.attachment = attachment
    
    # Send email
    response = sg.client.mail.send.post(request_body=message.get())

    if response.status_code == 202:
      logger.info(f"✅ Email sent successfully with property research results for addresses provided")
      print(f"✅ Email sent successfully to {recipient_email}")
    else:
        logger.error(f"❌ Failed to send email. Status code: {response.status_code}")
        print(f"❌ Failed to send email. Status code: {response.status_code}")
