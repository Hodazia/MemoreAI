'''
Now the document objects need to be chunked,

so remember for different file formats,
for pdf-> we have many document objects,for txt/docs we have 1
so we do we need different chunking stategies for them, or will just 1 Recursive textsplitter works fine!
'''

from langchain_text_splitters import RecursiveCharacterTextSplitter

def create_chunks(documents):
    '''
    split langchain documents into chunks
    '''

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )

    return splitter.split_documents(documents)