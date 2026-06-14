'''
So whatsapp sends, document_id,

We need:
    document_id
    Meta Media URL
    Actual Files
    uploads / 


What happens here?

Meta webhook sends:

{
  "document": {
    "id": "123456789"
  }
}

This ID is NOT the actual file.

You must first ask Meta:

GET
https://graph.facebook.com/v23.0/123456789

Meta responds:

{
  "url": "https://lookaside.fbsbx.com/..."
}

Now we can download.
'''

from config import ACCESS_TOKEN
import requests
import os

UPLOAD_DIR = "uploads"

def get_document_url(
    media_id:str):
    '''
    converts meta media id into downloadable URL
    
    so when we send the docuemnt from the chat, meta via the webhook sends an id in the document key,
    but that is not the media, we have to convert that into a downloadable url by again
    sending a request with that document id, to get the final url
    '''

    url = (
        f"https://graph.facebook.com/v25.0/{media_id}"
    )

    headers = {
        "Authorization":
        f"Bearer {ACCESS_TOKEN}"
    }

    response = requests.get(
        url,
        headers=headers
    )

    response.raise_for_status()

    data = response.json()

    return data["url"]

def download_document(media_url:str, filename:str):
    '''
    Download the documents from the media url and store it in a filename inside the uploads folder
    '''
    headers = {
        "Authorization":
        f"Bearer {ACCESS_TOKEN}"
    }

    filepath = os.path.join(
        UPLOAD_DIR,
        filename
        )

    response = requests.get(
        media_url,
        headers=headers,
        stream=True # downloads piece by piece
    )

    response.raise_for_status()

    with open(
        filepath,
        "wb"
    ) as file:

        for chunk in response.iter_content(
            chunk_size=8192
        ):
            file.write(chunk)

    return filepath


# this is a wrapper function which the post /webhook will call
'''
Webhook receives 
{
    "document": {
      "id": "111",
      "filename": "contract.pdf"
  }
}

then the below function gets called which results in
uploads/filename

'''
def save_whatsapp_document(
    media_id: str,
    filename: str
):
    """
    Main entrypoint
    """

    media_url = get_document_url(
        media_id
    )

    filepath = download_document(
        media_url,
        filename
    )

    return filepath
