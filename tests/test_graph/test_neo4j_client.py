"""Tests for Neo4jClient."""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from contextlib import contextmanager

from kg_forge.graph.neo4j_client import Neo4jClient
from kg_forge.graph.exceptions import Neo4jConnectionError, QueryError
from kg_forge.config.settings import Settings


def create_mock_session_context(session_mock):
    """Helper to create a proper context manager mock for Neo4j sessions."""
    context_mock = Mock()
    context_mock.__enter__ = Mock(return_value=session_mock)
    context_mock.__exit__ = Mock(return_value=None)
    return context_mock


class TestNeo4jClient:
    """Test Neo4j client functionality."""
    
    def setup_method(self):
        """Setup test fixtures."""
        # Create a mock settings object with neo4j config
        self.settings = Mock()
        self.settings.neo4j = Mock()
        self.settings.neo4j.uri = "bolt://localhost:7687"
        self.settings.neo4j.username = "neo4j"
        self.settings.neo4j.password = "password"
        self.settings.neo4j.database = "test_db"
        
    @patch('kg_forge.graph.neo4j_client.GraphDatabase')
    def test_init_with_settings(self, mock_graph_db):
        """Test client initialization with settings."""
        client = Neo4jClient(self.settings)
        
        assert client.config == self.settings.neo4j
        assert client.driver is None
        assert not client._connected
        
    @patch('kg_forge.config.settings.get_settings')
    @patch('kg_forge.graph.neo4j_client.GraphDatabase')
    def test_init_without_settings(self, mock_graph_db, mock_get_settings):
        """Test client initialization without explicit settings."""
        mock_get_settings.return_value = self.settings
        
        client = Neo4jClient()
        
        mock_get_settings.assert_called_once()
        assert client.config == self.settings.neo4j
        
    @patch('kg_forge.graph.neo4j_client.GraphDatabase')
    def test_connect_success(self, mock_graph_db):
        """Test successful database connection."""
        # Setup mocks
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()
        mock_record = Mock()
        mock_record.__getitem__ = Mock(return_value=1)
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        
        # Setup context manager for session
        mock_driver.session.return_value = create_mock_session_context(mock_session)
        mock_graph_db.driver.return_value = mock_driver
        
        client = Neo4jClient(self.settings)
        client.connect()
        
        # Verify connection setup
        mock_graph_db.driver.assert_called_once_with(
            "bolt://localhost:7687",
            auth=("neo4j", "password")
        )
        assert client.driver == mock_driver
        assert client._connected
        
        # Verify connection test
        mock_session.run.assert_called_once_with("RETURN 1 as test")
        
    @patch('kg_forge.graph.neo4j_client.GraphDatabase')
    def test_connect_already_connected(self, mock_graph_db):
        """Test connection when already connected."""
        client = Neo4jClient(self.settings)
        client._connected = True
        
        client.connect()
        
        # Should not attempt new connection
        mock_graph_db.driver.assert_not_called()
        
    @patch('kg_forge.graph.neo4j_client.GraphDatabase')
    def test_connect_service_unavailable(self, mock_graph_db):
        """Test connection failure due to service unavailable."""
        from neo4j.exceptions import ServiceUnavailable
        
        mock_graph_db.driver.side_effect = ServiceUnavailable("Connection failed")
        
        client = Neo4jClient(self.settings)
        
        with pytest.raises(Neo4jConnectionError) as exc_info:
            client.connect()
            
        assert "Cannot connect to Neo4j" in str(exc_info.value)
        assert "Is Neo4j running?" in str(exc_info.value)
        assert not client._connected
        
    @patch('kg_forge.graph.neo4j_client.GraphDatabase')
    def test_connect_auth_error(self, mock_graph_db):
        """Test connection failure due to authentication error."""
        from neo4j.exceptions import AuthError
        
        mock_graph_db.driver.side_effect = AuthError("Auth failed")
        
        client = Neo4jClient(self.settings)
        
        with pytest.raises(Neo4jConnectionError) as exc_info:
            client.connect()
            
        assert "Authentication failed" in str(exc_info.value)
        assert "Check your credentials" in str(exc_info.value)
        
    @patch('kg_forge.graph.neo4j_client.GraphDatabase')
    def test_disconnect(self, mock_graph_db):
        """Test database disconnection."""
        mock_driver = Mock()
        
        client = Neo4jClient(self.settings)
        client.driver = mock_driver
        client._connected = True
        
        client.disconnect()
        
        mock_driver.close.assert_called_once()
        assert client.driver is None
        assert not client._connected
        
    def test_disconnect_no_driver(self):
        """Test disconnection when no driver exists."""
        client = Neo4jClient(self.settings)
        
        # Should not raise exception
        client.disconnect()
        
    @patch('kg_forge.graph.neo4j_client.GraphDatabase')
    def test_test_connection_success(self, mock_graph_db):
        """Test successful connection test."""
        # Setup mocks
        mock_driver = Mock()
        mock_session = Mock()
        mock_result = Mock()
        mock_record = Mock()
        mock_record.__getitem__ = Mock(return_value="5.15.0")
        mock_result.single.return_value = mock_record
        mock_session.run.return_value = mock_result
        
        # Setup context manager for session
        mock_driver.session.return_value = create_mock_session_context(mock_session)
        
        client = Neo4jClient(self.settings)
        client.driver = mock_driver
        client._connected = True
        
        result = client.test_connection()
        
        assert result is True
        mock_session.run.assert_called_once()
        
    @patch('kg_forge.graph.neo4j_client.GraphDatabase')
    def test_test_connection_failure(self, mock_graph_db):
        """Test connection test failure."""
        mock_driver = Mock()
        mock_driver.session.side_effect = Exception("Connection failed")
        
        client = Neo4jClient(self.settings)
        client.driver = mock_driver
        client._connected = True
        
        result = client.test_connection()
        
        assert result is False
        
    @patch('kg_forge.graph.neo4j_client.GraphDatabase')
    def test_session_context_manager(self, mock_graph_db):
        """Test session context manager."""
        mock_driver = Mock()
        mock_session = Mock()
        mock_driver.session.return_value = mock_session
        
        client = Neo4jClient(self.settings)
        client.driver = mock_driver
        client._connected = True
        
        with client.session() as session:
            assert session == mock_session
            
        mock_session.close.assert_called_once()
        
    @patch('kg_forge.graph.neo4j_client.GraphDatabase')
    def test_session_auto_connect(self, mock_graph_db):
        """Test session auto-connects if not connected."""
        # Setup mocks for connection
        mock_driver = Mock()
        mock_session_connect = Mock()
        mock_session_use = Mock()
        mock_result = Mock()
        mock_record = Mock()
        mock_record.__getitem__ = Mock(return_value=1)
        mock_result.single.return_value = mock_record
        mock_session_connect.run.return_value = mock_result
        
        # Setup context managers for both sessions
        mock_connect_context = Mock()
        mock_connect_context.__enter__ = Mock(return_value=mock_session_connect)
        mock_connect_context.__exit__ = Mock(return_value=None)
        
        mock_use_context = Mock()
        mock_use_context.__enter__ = Mock(return_value=mock_session_use)
        mock_use_context.__exit__ = Mock(return_value=None)
        mock_driver.session.side_effect = [mock_connect_context, mock_use_context]
        mock_graph_db.driver.return_value = mock_driver
        
        # Setup context manager for connection test
        mock_connect_context = Mock()
        mock_connect_context.__enter__ = Mock(return_value=mock_session_connect)
        mock_connect_context.__exit__ = Mock(return_value=None)
        
        client = Neo4jClient(self.settings)
        
        with client.session() as session:
            # Should have auto-connected
            assert client._connected
            assert session is not None
            
    def test_execute_query_success(self):
        """Test successful query execution."""
        # Setup mocks
        mock_session = Mock()
        mock_records = [{"name": "test", "id": 1}]
        
        # Create a mock record object that has .data() method
        mock_record_obj = Mock()
        mock_record_obj.data.return_value = mock_records[0]
        
        # session.run() should return an iterable of record objects
        mock_session.run.return_value = [mock_record_obj]
        
        client = Neo4jClient(self.settings)
        
        # Directly mock the session method to avoid context manager complexity
        with patch.object(client, 'session') as mock_session_context:
            mock_session_context.return_value.__enter__.return_value = mock_session
            mock_session_context.return_value.__exit__.return_value = None
            
            result = client.execute_query("MATCH (n) RETURN n", {"param": "value"})
        
        assert result == mock_records
        mock_session.run.assert_called_once_with("MATCH (n) RETURN n", {"param": "value"})
        
    @patch('kg_forge.graph.neo4j_client.GraphDatabase')
    def test_execute_query_client_error(self, mock_graph_db):
        """Test query execution with client error."""
        from neo4j.exceptions import ClientError
        
        mock_driver = Mock()
        mock_session = Mock()
        mock_session.run.side_effect = ClientError("Query failed")
        mock_driver.session.return_value = create_mock_session_context(mock_session)
        
        client = Neo4jClient(self.settings)
        client.driver = mock_driver
        client._connected = True
        
        with pytest.raises(QueryError) as exc_info:
            client.execute_query("INVALID QUERY")
            
        # Check for either expected error message
        error_message = str(exc_info.value)
        assert "Query execution failed" in error_message or "Unexpected error during query execution" in error_message
        
    def test_clear_database_all(self):
        """Test clearing entire database."""
        # Create a proper record mock that has data() method
        mock_record_obj = Mock()
        mock_record_obj.data.return_value = {"deleted_count": 5}
        
        client = Neo4jClient(self.settings)
        client._connected = True
        
        # Mock the execute_query method directly
        with patch.object(client, 'execute_query') as mock_execute:
            mock_execute.return_value = [{"deleted_count": 5}]
            
            deleted_count = client.clear_database()
            
            assert deleted_count == 5
            # Verify the correct query was executed - just check it was called with empty dict
            args, kwargs = mock_execute.call_args
            assert "MATCH (n)" in args[0]
            assert "DETACH DELETE n" in args[0] 
            assert "RETURN count(n) as deleted_count" in args[0]
            assert args[1] == {}
        
    def test_clear_database_namespace(self):
        """Test clearing specific namespace."""
        client = Neo4jClient(self.settings)
        client._connected = True
        
        # Mock the execute_query method directly
        with patch.object(client, 'execute_query') as mock_execute:
            mock_execute.return_value = [{"deleted_count": 3}]
            
            deleted_count = client.clear_database("test_namespace")
            
            assert deleted_count == 3
            # Verify the correct query was executed
            args, kwargs = mock_execute.call_args
            assert "WHERE n.namespace = $namespace" in args[0]
            assert args[1] == {"namespace": "test_namespace"}
        
    def test_context_manager(self):
        """Test client as context manager."""
        client = Neo4jClient(self.settings)
        
        with patch.object(client, 'connect') as mock_connect, \
             patch.object(client, 'disconnect') as mock_disconnect:
            
            with client as c:
                assert c == client
                
            mock_connect.assert_called_once()
            mock_disconnect.assert_called_once()
