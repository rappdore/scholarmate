export interface Concept {
  id: number;
  book_id: number;
  book_type: 'epub' | 'pdf';
  name: string;
  definition: string | null;
  source_quote: string | null;
  importance: number; // 1-5
  nav_id: string | null; // For EPUB
  page_num: number | null; // For PDF
  created_at: string | null;
}

export interface ConceptCreate {
  book_id: number;
  book_type: 'epub' | 'pdf';
  name: string;
  definition?: string | null;
  source_quote?: string | null;
  importance?: number;
  nav_id?: string | null;
  page_num?: number | null;
}

export interface ConceptUpdate {
  definition?: string | null;
  source_quote?: string | null;
  importance?: number | null;
}

export type RelationshipType =
  | 'explains'
  | 'contrasts'
  | 'requires'
  | 'builds-on'
  | 'examples'
  | 'causes'
  | 'related-to';

export interface Relationship {
  id: number;
  source_concept_id: number;
  target_concept_id: number;
  relationship_type: RelationshipType;
  description: string | null;
  weight: number;
  created_at: string | null;
  // Joined fields (optional, populated when fetching with concept info)
  source_name?: string | null;
  source_definition?: string | null;
  target_name?: string | null;
  target_definition?: string | null;
}

export interface RelationshipCreate {
  source_concept_id: number;
  target_concept_id: number;
  relationship_type: RelationshipType;
  description?: string | null;
  weight?: number;
}

export interface RelationshipUpdate {
  relationship_type?: RelationshipType | null;
  description?: string | null;
  weight?: number | null;
}

export interface GraphNode {
  id: number;
  name: string;
  definition: string | null;
  importance: number;
  nav_id: string | null;
  page_num: number | null;
}

export interface GraphEdge {
  id: number;
  source: number;
  target: number;
  type: RelationshipType;
  description: string | null;
  weight: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface ExtractionRequest {
  book_id: number;
  book_type: 'epub' | 'pdf';
  nav_id?: string | null;
  page_num?: number | null;
}

export interface ExtractionResponse {
  concepts_extracted: number;
  relationships_found: number;
  section_id: string;
  already_extracted: boolean;
}

export interface BookExtractionRequest {
  book_id: number;
  book_type: 'epub' | 'pdf';
  force?: boolean;
  nav_ids?: string[] | null; // For EPUBs
  page_start?: number | null; // For PDFs
  page_end?: number | null; // For PDFs
}

export interface BookExtractionResponse {
  total_sections: number;
  sections_extracted: number;
  sections_skipped: number;
  concepts_extracted: number;
  relationships_found: number;
  errors: string[];
}

export interface ExtractionProgress {
  id: number;
  book_id: number;
  book_type: 'epub' | 'pdf';
  nav_id: string | null;
  page_num: number | null;
  extracted_at: string;
}

export interface KnowledgeStats {
  total_concepts: number;
  total_relationships: number;
  total_flashcards: number;
  sections_extracted: number;
}

// Extraction status types for real-time progress tracking
export type ExtractionStatusType =
  | 'pending'
  | 'running'
  | 'cancelling'
  | 'cancelled'
  | 'completed'
  | 'failed';

export interface ExtractionStatusInfo {
  book_id: number;
  book_type: 'epub' | 'pdf';
  section_id: string;
  status: ExtractionStatusType;
  started_at: number;
  elapsed_seconds: number;
  chunks_processed: number;
  total_chunks: number;
  concepts_stored: number;
  progress_percent: number;
  error_message: string | null;
}

export interface ExtractionStatusResponse {
  found?: boolean;
  message?: string;
  extraction?: ExtractionStatusInfo;
  count?: number;
  extractions?: ExtractionStatusInfo[];
}

export interface CancelExtractionResponse {
  success: boolean;
  message: string;
  book_id: number;
  section_id?: string;
  extractions_cancelled?: number;
}
