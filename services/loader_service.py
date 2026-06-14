'''
We will load the different format of files in the Document object, 
be it pdf, docx, txt !

'''

from pathlib import Path

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader
)

def load_documents(filepath:str):
    '''
    Load the documents in Langchain document format
    '''

    # extract the extension of the file and accordingly write the different loaders
    extension = Path(filepath).suffix().lower()

    # for pdf , if u have a 10 page pdf, then u will get 10 Document objects
    if extension == ".pdf":

        loader = PyPDFLoader(
            filepath
        )

    # for txt, we will be getting only 1 Document object,regardless of the size of the txt file
    # loader.load() will return a list of only 1 Document object
    elif extension == ".txt":

        loader = TextLoader(
            filepath,
            encoding="utf-8"
        )

    # for docx , it will be the same as .txt file
    elif extension == ".docx":

        loader = Docx2txtLoader(
            filepath
        )

    else:

        raise ValueError(
            f"Unsupported file: {extension}"
        )

    return loader.load()