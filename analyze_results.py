#!/usr/bin/env python3

from neo4j import GraphDatabase
import json

def analyze_spacy_results():
    """Analyze the results of the spaCy full pipeline ingestion."""
    driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'password'))

    with driver.session() as session:
        print("=== spaCy Pipeline Results Analysis ===")
        print()
        
        # Get entity counts by type
        result = session.run('''
            MATCH (e:Entity {namespace: 'spacytest'})
            RETURN e.entity_type as type, count(*) as count
            ORDER BY count DESC
        ''')
        
        print('Entity counts by type:')
        total_entities = 0
        for record in result:
            count = record['count']
            total_entities += count
            print(f'  {record["type"]}: {count}')
        
        print(f'\nTotal entities: {total_entities}')
        print()
        
        # Get sample entities with their mention counts and deduplication info
        result = session.run('''
            MATCH (e:Entity {namespace: 'spacytest'})
            OPTIONAL MATCH (d:Doc)-[m:MENTIONS]->(e)
            WITH e, count(m) as mention_count
            RETURN e.entity_type as type, e.name as name, e.normalized_name as normalized_name, 
                   mention_count, e.aliases as aliases, e.mention_count as total_mentions
            ORDER BY mention_count DESC, e.name
        ''')
        
        print('Entities with mention details:')
        entities_with_multiple_mentions = 0
        entities_with_aliases = 0
        
        for record in result:
            aliases = record['aliases'] or []
            mention_count = record['mention_count']
            total_mentions = record['total_mentions'] or 0
            
            print(f'  • {record["name"]} ({record["type"]})')
            print(f'    - Doc mentions: {mention_count}, Total mentions: {total_mentions}')
            
            if len(aliases) > 1:
                entities_with_aliases += 1
                print(f'    - Aliases: {aliases}')
            
            if mention_count > 1:
                entities_with_multiple_mentions += 1
                
        print(f'\nDeduplication Analysis:')
        print(f'  Entities with multiple document mentions: {entities_with_multiple_mentions}')
        print(f'  Entities with aliases (deduped): {entities_with_aliases}')
        print()
        
        # Check document processing
        result = session.run('''
            MATCH (d:Doc {namespace: 'spacytest'})
            OPTIONAL MATCH (d)-[m:MENTIONS]->(e:Entity)
            WITH d, count(e) as entity_count
            RETURN d.doc_id as doc_id, d.title as title, entity_count
            ORDER BY entity_count DESC
        ''')
        
        print('Document processing results:')
        total_docs = 0
        for record in result:
            total_docs += 1
            print(f'  • {record["doc_id"]}')
            print(f'    Title: {record["title"]}')
            print(f'    Entities extracted: {record["entity_count"]}')
            
        print(f'\nTotal documents processed: {total_docs}')
        print()
        
        # Check for any domain relations (though we expect 0)
        result = session.run('''
            MATCH (e1:Entity {namespace: 'spacytest'})-[r]->(e2:Entity {namespace: 'spacytest'})
            WHERE type(r) <> 'MENTIONS'
            RETURN type(r) as relation_type, e1.name as from_entity, e2.name as to_entity
            LIMIT 10
        ''')
        
        relations = list(result)
        if relations:
            print('Entity-to-entity relations found:')
            for record in relations:
                print(f'  {record["from_entity"]} --{record["relation_type"]}--> {record["to_entity"]}')
        else:
            print('No entity-to-entity relations found (expected for this test)')
        
        print()

    driver.close()

if __name__ == "__main__":
    analyze_spacy_results()