# Upload notes

When a document is uploaded:
- it is converted to markdown
- split into chunks
- embeddings are generated
- chunks are stored in the database

The chat endpoint retrieves relevant chunks based on similarity search.
