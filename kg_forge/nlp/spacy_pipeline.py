"""
spaCy pipeline integration for document processing.

Provides text processing, tokenization, and sentence segmentation.
"""
from typing import Dict, Any, List, Optional, Tuple
import logging

# spaCy imports with fallback
try:
    import spacy
    from spacy.tokens import Doc, Span, Token
    from spacy.lang.en import English
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None
    Doc = Span = Token = English = None

from kg_forge.extraction.exceptions import BackendNotAvailableError, ModelLoadingError

logger = logging.getLogger(__name__)


class SpacyPipeline:
    """spaCy pipeline wrapper for text processing."""
    
    def __init__(self, 
                 model_name: str = "en_core_web_sm",
                 disable_components: List[str] = None):
        """Initialize spaCy pipeline.
        
        Args:
            model_name: spaCy model name to load
            disable_components: Components to disable for performance
        """
        if not SPACY_AVAILABLE:
            raise BackendNotAvailableError(
                "spaCy not available. Install with: pip install spacy"
            )
        
        self.model_name = model_name
        self.disable_components = disable_components or ["ner", "parser"]  # We'll use GLiNER for NER
        
        self.nlp = None
        self._load_model()
    
    def _load_model(self):
        """Load the spaCy model."""
        try:
            logger.info(f"Loading spaCy model: {self.model_name}")
            
            # Try to load the model
            self.nlp = spacy.load(self.model_name, disable=self.disable_components)
            
            # Add custom components if needed
            self._configure_pipeline()
            
            logger.info(f"spaCy pipeline loaded successfully", extra={
                "model": self.model_name,
                "components": list(self.nlp.pipe_names),
                "disabled": self.disable_components
            })
            
        except OSError as e:
            # Model not found
            if "Can't find model" in str(e) or "No such file or directory" in str(e):
                raise ModelLoadingError(
                    f"spaCy model '{self.model_name}' not found. "
                    f"Install with: python -m spacy download {self.model_name}"
                )
            else:
                raise ModelLoadingError(f"Failed to load spaCy model: {e}")
        
        except Exception as e:
            raise ModelLoadingError(f"Unexpected error loading spaCy model: {e}")
    
    def _configure_pipeline(self):
        """Configure the spaCy pipeline with custom components."""
        # Add sentence segmentation if not present
        if "sentencizer" not in self.nlp.pipe_names and "parser" not in self.nlp.pipe_names:
            self.nlp.add_pipe("sentencizer")
            logger.debug("Added sentencizer component to spaCy pipeline")
    
    def process(self, text: str) -> Doc:
        """Process text through spaCy pipeline.
        
        Args:
            text: Input text to process
        
        Returns:
            spaCy Doc object with tokens, sentences, etc.
        
        Raises:
            ModelLoadingError: If processing fails
        """
        if not self.nlp:
            raise ModelLoadingError("spaCy model not loaded")
        
        try:
            doc = self.nlp(text)
            
            logger.debug(f"Processed text through spaCy", extra={
                "text_length": len(text),
                "tokens": len(doc),
                "sentences": len(list(doc.sents))
            })
            
            return doc
            
        except Exception as e:
            raise ModelLoadingError(f"spaCy processing failed: {e}")
    
    def get_tokens_info(self, doc: Doc) -> List[Dict[str, Any]]:
        """Extract token information from spaCy doc.
        
        Args:
            doc: Processed spaCy document
        
        Returns:
            List of token dictionaries with text, position, POS, etc.
        """
        tokens = []
        
        for token in doc:
            token_info = {
                "text": token.text,
                "lemma": token.lemma_,
                "pos": token.pos_,
                "tag": token.tag_,
                "start_char": token.idx,
                "end_char": token.idx + len(token.text),
                "is_alpha": token.is_alpha,
                "is_stop": token.is_stop,
                "is_punct": token.is_punct,
                "sentence_idx": self._get_sentence_index(token)
            }
            tokens.append(token_info)
        
        return tokens
    
    def get_sentences_info(self, doc: Doc) -> List[Dict[str, Any]]:
        """Extract sentence information from spaCy doc.
        
        Args:
            doc: Processed spaCy document
        
        Returns:
            List of sentence dictionaries with text and boundaries
        """
        sentences = []
        
        for i, sent in enumerate(doc.sents):
            sentence_info = {
                "index": i,
                "text": sent.text,
                "start_char": sent.start_char,
                "end_char": sent.end_char,
                "start_token": sent.start,
                "end_token": sent.end,
                "length": len(sent.text)
            }
            sentences.append(sentence_info)
        
        return sentences
    
    def _get_sentence_index(self, token: Token) -> int:
        """Get sentence index for a token.
        
        Args:
            token: spaCy token
        
        Returns:
            Sentence index (0-based)
        """
        for i, sent in enumerate(token.doc.sents):
            if sent.start <= token.i < sent.end:
                return i
        return -1
    
    def get_context_around_span(self, doc: Doc, start_char: int, end_char: int, 
                              context_words: int = 5) -> Dict[str, Any]:
        """Get context around a character span.
        
        Args:
            doc: spaCy document
            start_char: Start character position
            end_char: End character position
            context_words: Number of words to include on each side
        
        Returns:
            Dictionary with context information
        """
        # Find tokens that overlap with the span
        span_tokens = []
        for token in doc:
            if token.idx < end_char and token.idx + len(token.text) > start_char:
                span_tokens.append(token)
        
        if not span_tokens:
            return {
                "before_context": "",
                "after_context": "",
                "sentence_text": "",
                "sentence_index": -1
            }
        
        # Get sentence containing the span
        first_token = span_tokens[0]
        sentence = first_token.sent
        
        # Find context tokens
        first_token_idx = span_tokens[0].i
        last_token_idx = span_tokens[-1].i
        
        # Before context
        before_start = max(sentence.start, first_token_idx - context_words)
        before_tokens = doc[before_start:first_token_idx]
        before_context = " ".join([t.text for t in before_tokens])
        
        # After context
        after_end = min(sentence.end, last_token_idx + 1 + context_words)
        after_tokens = doc[last_token_idx + 1:after_end]
        after_context = " ".join([t.text for t in after_tokens])
        
        return {
            "before_context": before_context,
            "after_context": after_context,
            "sentence_text": sentence.text,
            "sentence_index": self._get_sentence_index(first_token)
        }
    
    def char_span_to_token_span(self, doc: Doc, start_char: int, 
                               end_char: int) -> Optional[Tuple[int, int]]:
        """Convert character span to token span.
        
        Args:
            doc: spaCy document
            start_char: Start character position
            end_char: End character position
        
        Returns:
            Tuple of (start_token_idx, end_token_idx) or None if no match
        """
        start_token = None
        end_token = None
        
        for token in doc:
            # Find start token
            if start_token is None and token.idx <= start_char < token.idx + len(token.text):
                start_token = token.i
            
            # Find end token
            if token.idx < end_char <= token.idx + len(token.text):
                end_token = token.i + 1  # End is exclusive
                break
        
        if start_token is not None and end_token is not None:
            return (start_token, end_token)
        
        return None
    
    def validate_model(self) -> bool:
        """Validate that the spaCy model is working properly.
        
        Returns:
            True if model validation passes
        """
        try:
            # Test with simple text
            test_doc = self.process("This is a test sentence.")
            
            # Check basic functionality
            if len(test_doc) == 0:
                return False
            
            # Check if we have sentence segmentation
            sentences = list(test_doc.sents)
            if len(sentences) == 0:
                return False
            
            logger.info("spaCy model validation passed")
            return True
            
        except Exception as e:
            logger.error(f"spaCy model validation failed: {e}")
            return False
    
    def get_pipeline_info(self) -> Dict[str, Any]:
        """Get information about the loaded pipeline.
        
        Returns:
            Dictionary with pipeline details
        """
        if not self.nlp:
            return {"loaded": False, "error": "Model not loaded"}
        
        return {
            "loaded": True,
            "model_name": self.model_name,
            "components": list(self.nlp.pipe_names),
            "disabled_components": self.disable_components,
            "lang": self.nlp.lang,
            "vocab_size": len(self.nlp.vocab),
            "has_vectors": self.nlp.vocab.vectors.size > 0 if hasattr(self.nlp.vocab, 'vectors') else False
        }


class FakeSpacyPipeline:
    """Fake spaCy pipeline for testing when spaCy is not available."""
    
    def __init__(self, model_name: str = "fake_en", disable_components: List[str] = None):
        """Initialize fake pipeline."""
        self.model_name = model_name
        self.disable_components = disable_components or []
    
    def process(self, text: str) -> "FakeDoc":
        """Process text and return fake doc."""
        return FakeDoc(text)
    
    def get_tokens_info(self, doc: "FakeDoc") -> List[Dict[str, Any]]:
        """Get fake token information."""
        words = doc.text.split()
        tokens = []
        
        char_pos = 0
        for i, word in enumerate(words):
            # Skip spaces at the beginning
            while char_pos < len(doc.text) and doc.text[char_pos].isspace():
                char_pos += 1
            
            tokens.append({
                "text": word,
                "lemma": word.lower(),
                "pos": "NOUN" if word.isalpha() else "PUNCT",
                "tag": "NN",
                "start_char": char_pos,
                "end_char": char_pos + len(word),
                "is_alpha": word.isalpha(),
                "is_stop": word.lower() in ["the", "a", "an", "and", "or", "but"],
                "is_punct": not word.isalpha(),
                "sentence_idx": 0
            })
            
            char_pos += len(word)
        
        return tokens
    
    def get_sentences_info(self, doc: "FakeDoc") -> List[Dict[str, Any]]:
        """Get fake sentence information."""
        return [{
            "index": 0,
            "text": doc.text,
            "start_char": 0,
            "end_char": len(doc.text),
            "start_token": 0,
            "end_token": len(doc.text.split()),
            "length": len(doc.text)
        }]
    
    def get_context_around_span(self, doc: "FakeDoc", start_char: int, end_char: int, 
                              context_words: int = 5) -> Dict[str, Any]:
        """Get fake context."""
        return {
            "before_context": "fake before",
            "after_context": "fake after", 
            "sentence_text": doc.text,
            "sentence_index": 0
        }
    
    def validate_model(self) -> bool:
        """Fake validation always passes."""
        return True
    
    def get_pipeline_info(self) -> Dict[str, Any]:
        """Get fake pipeline info."""
        return {
            "loaded": True,
            "model_name": self.model_name,
            "components": ["fake_tokenizer", "fake_sentencizer"],
            "disabled_components": self.disable_components,
            "fake": True
        }


class FakeDoc:
    """Fake spaCy Doc for testing."""
    
    def __init__(self, text: str):
        self.text = text