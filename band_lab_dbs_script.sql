--
-- PostgreSQL database dump
--

\restrict P0RGL5UrSuc1QeZOUzFuhhJjtQA4RTnAos3pOdWJFJP1D9mH4mchVreetFtP8EL

-- Dumped from database version 16.14
-- Dumped by pg_dump version 18.3

-- Started on 2026-06-16 20:48:47

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 2 (class 3079 OID 16471)
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- TOC entry 4907 (class 0 OID 0)
-- Dependencies: 2
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 234 (class 1259 OID 17099)
-- Name: agent_conflict; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.agent_conflict (
    conflict_id uuid DEFAULT gen_random_uuid() NOT NULL,
    cycle_id uuid NOT NULL,
    vendor_id uuid NOT NULL,
    agent_a character varying(50) NOT NULL,
    agent_b character varying(50) NOT NULL,
    conflict_description text NOT NULL,
    resolution_status character varying(30) DEFAULT 'pending'::character varying,
    resolution_notes text,
    resolved_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.agent_conflict OWNER TO doadmin;

--
-- TOC entry 233 (class 1259 OID 17069)
-- Name: agent_finding; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.agent_finding (
    finding_id uuid DEFAULT gen_random_uuid() NOT NULL,
    vendor_id uuid NOT NULL,
    cycle_id uuid NOT NULL,
    agent_type character varying(50) NOT NULL,
    dimension character varying(100) NOT NULL,
    regulation_code character varying(100),
    score numeric,
    severity character varying(20),
    finding_summary text NOT NULL,
    evidence_quote text,
    evidence_page integer,
    evidence_chunk_id uuid,
    is_dealbreaker boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.agent_finding OWNER TO doadmin;

--
-- TOC entry 236 (class 1259 OID 17134)
-- Name: audit_log; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.audit_log (
    log_id uuid DEFAULT gen_random_uuid() NOT NULL,
    cycle_id uuid,
    vendor_id uuid,
    event_type character varying(50) NOT NULL,
    agent_type character varying(50),
    detail jsonb,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.audit_log OWNER TO doadmin;

--
-- TOC entry 229 (class 1259 OID 16993)
-- Name: cycle_context; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.cycle_context (
    context_id uuid DEFAULT gen_random_uuid() NOT NULL,
    cycle_id uuid NOT NULL,
    software_type character varying(255),
    software_category_code character varying(50),
    data_sensitivity_code character varying(50),
    estimated_contract_value numeric,
    discovery_summary text,
    evidence_sources jsonb,
    confidence_score numeric,
    requires_confirmation boolean DEFAULT false,
    confirmed_by_user boolean DEFAULT false,
    confirmed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.cycle_context OWNER TO doadmin;

--
-- TOC entry 218 (class 1259 OID 16815)
-- Name: data_sensitivity; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.data_sensitivity (
    sensitivity_code character varying(50) NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.data_sensitivity OWNER TO doadmin;

--
-- TOC entry 232 (class 1259 OID 17055)
-- Name: document_chunk; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.document_chunk (
    chunk_id uuid DEFAULT gen_random_uuid() NOT NULL,
    document_id uuid NOT NULL,
    chunk_index integer NOT NULL,
    page_start integer,
    page_end integer,
    section_heading text,
    content text NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    embedding public.vector(1536),
    embedding_model character varying(100),
    embedded_at timestamp without time zone
);


ALTER TABLE public.document_chunk OWNER TO doadmin;

--
-- TOC entry 221 (class 1259 OID 16857)
-- Name: document_type; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.document_type (
    document_type_code character varying(100) NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    is_baseline boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.document_type OWNER TO doadmin;

--
-- TOC entry 237 (class 1259 OID 17155)
-- Name: embedding_job; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.embedding_job (
    job_id uuid DEFAULT gen_random_uuid() NOT NULL,
    chunk_id uuid NOT NULL,
    status character varying(30) DEFAULT 'pending'::character varying,
    error_message text,
    attempts integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT now(),
    completed_at timestamp without time zone
);


ALTER TABLE public.embedding_job OWNER TO doadmin;

--
-- TOC entry 216 (class 1259 OID 16799)
-- Name: enterprise; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.enterprise (
    enterprise_id uuid NOT NULL,
    name character varying(255) NOT NULL,
    country_code character(2) NOT NULL,
    industry_code character varying(50) NOT NULL,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.enterprise OWNER TO doadmin;

--
-- TOC entry 223 (class 1259 OID 16885)
-- Name: enterprise_regulation; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.enterprise_regulation (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    enterprise_id uuid NOT NULL,
    regulation_code character varying(100) NOT NULL,
    is_mandatory boolean DEFAULT true,
    added_by character varying(50) DEFAULT 'system'::character varying,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.enterprise_regulation OWNER TO doadmin;

--
-- TOC entry 225 (class 1259 OID 16920)
-- Name: policy_document_requirement; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.policy_document_requirement (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    policy_id uuid NOT NULL,
    document_type_code character varying(100),
    custom_document_name character varying(255),
    is_mandatory boolean DEFAULT true,
    consequence_if_missing character varying(50) DEFAULT 'flag'::character varying,
    contract_value_threshold numeric,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.policy_document_requirement OWNER TO doadmin;

--
-- TOC entry 226 (class 1259 OID 16941)
-- Name: policy_evaluation_rule; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.policy_evaluation_rule (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    policy_id uuid NOT NULL,
    agent_type character varying(50) NOT NULL,
    rule_description text NOT NULL,
    severity character varying(20) DEFAULT 'medium'::character varying,
    is_dealbreaker boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.policy_evaluation_rule OWNER TO doadmin;

--
-- TOC entry 227 (class 1259 OID 16957)
-- Name: policy_weight_config; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.policy_weight_config (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    policy_id uuid NOT NULL,
    financial_weight numeric DEFAULT 0.25,
    legal_weight numeric DEFAULT 0.25,
    security_weight numeric DEFAULT 0.25,
    technical_weight numeric DEFAULT 0.25,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.policy_weight_config OWNER TO doadmin;

--
-- TOC entry 228 (class 1259 OID 16975)
-- Name: procurement_cycle; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.procurement_cycle (
    cycle_id uuid DEFAULT gen_random_uuid() NOT NULL,
    enterprise_id uuid NOT NULL,
    policy_id uuid,
    title character varying(255) NOT NULL,
    status character varying(30) DEFAULT 'active'::character varying,
    created_at timestamp without time zone DEFAULT now(),
    completed_at timestamp without time zone
);


ALTER TABLE public.procurement_cycle OWNER TO doadmin;

--
-- TOC entry 224 (class 1259 OID 16904)
-- Name: procurement_policy; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.procurement_policy (
    policy_id uuid DEFAULT gen_random_uuid() NOT NULL,
    enterprise_id uuid NOT NULL,
    policy_name character varying(255),
    raw_text text,
    parsed_at timestamp without time zone,
    parsed_by character varying(50) DEFAULT 'policy_parser_agent'::character varying,
    status character varying(20) DEFAULT 'pending'::character varying,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.procurement_policy OWNER TO doadmin;

--
-- TOC entry 235 (class 1259 OID 17119)
-- Name: recommendation; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.recommendation (
    recommendation_id uuid DEFAULT gen_random_uuid() NOT NULL,
    cycle_id uuid NOT NULL,
    vendor_ranking jsonb NOT NULL,
    executive_summary text NOT NULL,
    tradeoff_notes text,
    confidence_score numeric,
    requires_escalation boolean DEFAULT false,
    generated_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.recommendation OWNER TO doadmin;
--

CREATE TABLE public.regulation_framework (
    regulation_code character varying(100) NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    country_code character(2),
    industry_code character varying(50),
    software_category_code character varying(50),
    data_sensitivity_code character varying(50),
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.regulation_framework OWNER TO doadmin;

--
-- TOC entry 220 (class 1259 OID 16841)
-- Name: regulation_rule; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.regulation_rule (
    rule_id uuid DEFAULT gen_random_uuid() NOT NULL,
    regulation_code character varying(100) NOT NULL,
    agent_type character varying(50) NOT NULL,
    rule_description text NOT NULL,
    severity character varying(20) DEFAULT 'high'::character varying,
    is_dealbreaker boolean DEFAULT false,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.regulation_rule OWNER TO doadmin;

--
-- TOC entry 217 (class 1259 OID 16807)
-- Name: software_category; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.software_category (
    category_code character varying(50) NOT NULL,
    name character varying(255) NOT NULL,
    description text,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.software_category OWNER TO doadmin;

--
-- TOC entry 230 (class 1259 OID 17019)
-- Name: vendor; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.vendor (
    vendor_id uuid DEFAULT gen_random_uuid() NOT NULL,
    cycle_id uuid NOT NULL,
    vendor_name character varying(255) NOT NULL,
    submission_status character varying(30) DEFAULT 'incomplete'::character varying,
    completeness_score numeric,
    created_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.vendor OWNER TO doadmin;

--
-- TOC entry 231 (class 1259 OID 17034)
-- Name: vendor_document; Type: TABLE; Schema: public; Owner: doadmin
--

CREATE TABLE public.vendor_document (
    document_id uuid DEFAULT gen_random_uuid() NOT NULL,
    vendor_id uuid NOT NULL,
    document_type_code character varying(100),
    custom_document_name character varying(255),
    file_path text NOT NULL,
    language_code character(5) DEFAULT 'en'::bpchar,
    extraction_status character varying(30) DEFAULT 'pending'::character varying,
    extracted_text text,
    page_count integer,
    uploaded_at timestamp without time zone DEFAULT now()
);


ALTER TABLE public.vendor_document OWNER TO doadmin;

--
-- TOC entry 4721 (class 2606 OID 17108)
-- Name: agent_conflict agent_conflict_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.agent_conflict
    ADD CONSTRAINT agent_conflict_pkey PRIMARY KEY (conflict_id);


--
-- TOC entry 4719 (class 2606 OID 17078)
-- Name: agent_finding agent_finding_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.agent_finding
    ADD CONSTRAINT agent_finding_pkey PRIMARY KEY (finding_id);


--
-- TOC entry 4725 (class 2606 OID 17142)
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (log_id);


--
-- TOC entry 4710 (class 2606 OID 17003)
-- Name: cycle_context cycle_context_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.cycle_context
    ADD CONSTRAINT cycle_context_pkey PRIMARY KEY (context_id);


--
-- TOC entry 4688 (class 2606 OID 16822)
-- Name: data_sensitivity data_sensitivity_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.data_sensitivity
    ADD CONSTRAINT data_sensitivity_pkey PRIMARY KEY (sensitivity_code);


--
-- TOC entry 4716 (class 2606 OID 17063)
-- Name: document_chunk document_chunk_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.document_chunk
    ADD CONSTRAINT document_chunk_pkey PRIMARY KEY (chunk_id);


--
-- TOC entry 4694 (class 2606 OID 16865)
-- Name: document_type document_type_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.document_type
    ADD CONSTRAINT document_type_pkey PRIMARY KEY (document_type_code);


--
-- TOC entry 4727 (class 2606 OID 17165)
-- Name: embedding_job embedding_job_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.embedding_job
    ADD CONSTRAINT embedding_job_pkey PRIMARY KEY (job_id);


--
-- TOC entry 4684 (class 2606 OID 16804)
-- Name: enterprise enterprise_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.enterprise
    ADD CONSTRAINT enterprise_pkey PRIMARY KEY (enterprise_id);


--
-- TOC entry 4698 (class 2606 OID 16893)
-- Name: enterprise_regulation enterprise_regulation_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.enterprise_regulation
    ADD CONSTRAINT enterprise_regulation_pkey PRIMARY KEY (id);


--
-- TOC entry 4702 (class 2606 OID 16930)
-- Name: policy_document_requirement policy_document_requirement_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.policy_document_requirement
    ADD CONSTRAINT policy_document_requirement_pkey PRIMARY KEY (id);


--
-- TOC entry 4704 (class 2606 OID 16951)
-- Name: policy_evaluation_rule policy_evaluation_rule_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.policy_evaluation_rule
    ADD CONSTRAINT policy_evaluation_rule_pkey PRIMARY KEY (id);


--
-- TOC entry 4706 (class 2606 OID 16969)
-- Name: policy_weight_config policy_weight_config_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.policy_weight_config
    ADD CONSTRAINT policy_weight_config_pkey PRIMARY KEY (id);


--
-- TOC entry 4708 (class 2606 OID 16982)
-- Name: procurement_cycle procurement_cycle_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.procurement_cycle
    ADD CONSTRAINT procurement_cycle_pkey PRIMARY KEY (cycle_id);


--
-- TOC entry 4700 (class 2606 OID 16914)
-- Name: procurement_policy procurement_policy_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.procurement_policy
    ADD CONSTRAINT procurement_policy_pkey PRIMARY KEY (policy_id);


--
-- TOC entry 4723 (class 2606 OID 17128)
-- Name: recommendation recommendation_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.recommendation
    ADD CONSTRAINT recommendation_pkey PRIMARY KEY (recommendation_id);


--
-- TOC entry 4696 (class 2606 OID 16874)
-- Name: regulation_document_requirement regulation_document_requirement_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.regulation_document_requirement
    ADD CONSTRAINT regulation_document_requirement_pkey PRIMARY KEY (id);


--
-- TOC entry 4690 (class 2606 OID 16830)
-- Name: regulation_framework regulation_framework_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.regulation_framework
    ADD CONSTRAINT regulation_framework_pkey PRIMARY KEY (regulation_code);


--
-- TOC entry 4692 (class 2606 OID 16851)
-- Name: regulation_rule regulation_rule_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.regulation_rule
    ADD CONSTRAINT regulation_rule_pkey PRIMARY KEY (rule_id);


--
-- TOC entry 4686 (class 2606 OID 16814)
-- Name: software_category software_category_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.software_category
    ADD CONSTRAINT software_category_pkey PRIMARY KEY (category_code);


--
-- TOC entry 4714 (class 2606 OID 17044)
-- Name: vendor_document vendor_document_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.vendor_document
    ADD CONSTRAINT vendor_document_pkey PRIMARY KEY (document_id);


--
-- TOC entry 4712 (class 2606 OID 17028)
-- Name: vendor vendor_pkey; Type: CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.vendor
    ADD CONSTRAINT vendor_pkey PRIMARY KEY (vendor_id);


--
-- TOC entry 4717 (class 1259 OID 17154)
-- Name: idx_document_chunk_embedding; Type: INDEX; Schema: public; Owner: doadmin
--

CREATE INDEX idx_document_chunk_embedding ON public.document_chunk USING ivfflat (embedding public.vector_cosine_ops) WITH (lists='100');


--
-- TOC entry 4753 (class 2606 OID 17109)
-- Name: agent_conflict agent_conflict_cycle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.agent_conflict
    ADD CONSTRAINT agent_conflict_cycle_id_fkey FOREIGN KEY (cycle_id) REFERENCES public.procurement_cycle(cycle_id);


--
-- TOC entry 4754 (class 2606 OID 17114)
-- Name: agent_conflict agent_conflict_vendor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.agent_conflict
    ADD CONSTRAINT agent_conflict_vendor_id_fkey FOREIGN KEY (vendor_id) REFERENCES public.vendor(vendor_id);


--
-- TOC entry 4749 (class 2606 OID 17084)
-- Name: agent_finding agent_finding_cycle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.agent_finding
    ADD CONSTRAINT agent_finding_cycle_id_fkey FOREIGN KEY (cycle_id) REFERENCES public.procurement_cycle(cycle_id);


--
-- TOC entry 4750 (class 2606 OID 17094)
-- Name: agent_finding agent_finding_evidence_chunk_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.agent_finding
    ADD CONSTRAINT agent_finding_evidence_chunk_id_fkey FOREIGN KEY (evidence_chunk_id) REFERENCES public.document_chunk(chunk_id);


--
-- TOC entry 4751 (class 2606 OID 17089)
-- Name: agent_finding agent_finding_regulation_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.agent_finding
    ADD CONSTRAINT agent_finding_regulation_code_fkey FOREIGN KEY (regulation_code) REFERENCES public.regulation_framework(regulation_code);


--
-- TOC entry 4752 (class 2606 OID 17079)
-- Name: agent_finding agent_finding_vendor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.agent_finding
    ADD CONSTRAINT agent_finding_vendor_id_fkey FOREIGN KEY (vendor_id) REFERENCES public.vendor(vendor_id);


--
-- TOC entry 4756 (class 2606 OID 17143)
-- Name: audit_log audit_log_cycle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_cycle_id_fkey FOREIGN KEY (cycle_id) REFERENCES public.procurement_cycle(cycle_id);


--
-- TOC entry 4757 (class 2606 OID 17148)
-- Name: audit_log audit_log_vendor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_vendor_id_fkey FOREIGN KEY (vendor_id) REFERENCES public.vendor(vendor_id);


--
-- TOC entry 4742 (class 2606 OID 17004)
-- Name: cycle_context cycle_context_cycle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.cycle_context
    ADD CONSTRAINT cycle_context_cycle_id_fkey FOREIGN KEY (cycle_id) REFERENCES public.procurement_cycle(cycle_id);


--
-- TOC entry 4743 (class 2606 OID 17014)
-- Name: cycle_context cycle_context_data_sensitivity_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.cycle_context
    ADD CONSTRAINT cycle_context_data_sensitivity_code_fkey FOREIGN KEY (data_sensitivity_code) REFERENCES public.data_sensitivity(sensitivity_code);


--
-- TOC entry 4744 (class 2606 OID 17009)
-- Name: cycle_context cycle_context_software_category_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.cycle_context
    ADD CONSTRAINT cycle_context_software_category_code_fkey FOREIGN KEY (software_category_code) REFERENCES public.software_category(category_code);


--
-- TOC entry 4748 (class 2606 OID 17064)
-- Name: document_chunk document_chunk_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.document_chunk
    ADD CONSTRAINT document_chunk_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.vendor_document(document_id);


--
-- TOC entry 4758 (class 2606 OID 17166)
-- Name: embedding_job embedding_job_chunk_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.embedding_job
    ADD CONSTRAINT embedding_job_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES public.document_chunk(chunk_id);


--
-- TOC entry 4733 (class 2606 OID 16894)
-- Name: enterprise_regulation enterprise_regulation_enterprise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.enterprise_regulation
    ADD CONSTRAINT enterprise_regulation_enterprise_id_fkey FOREIGN KEY (enterprise_id) REFERENCES public.enterprise(enterprise_id);


--
-- TOC entry 4734 (class 2606 OID 16899)
-- Name: enterprise_regulation enterprise_regulation_regulation_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.enterprise_regulation
    ADD CONSTRAINT enterprise_regulation_regulation_code_fkey FOREIGN KEY (regulation_code) REFERENCES public.regulation_framework(regulation_code);


--
-- TOC entry 4736 (class 2606 OID 16936)
-- Name: policy_document_requirement policy_document_requirement_document_type_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.policy_document_requirement
    ADD CONSTRAINT policy_document_requirement_document_type_code_fkey FOREIGN KEY (document_type_code) REFERENCES public.document_type(document_type_code);


--
-- TOC entry 4737 (class 2606 OID 16931)
-- Name: policy_document_requirement policy_document_requirement_policy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.policy_document_requirement
    ADD CONSTRAINT policy_document_requirement_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES public.procurement_policy(policy_id);


--
-- TOC entry 4738 (class 2606 OID 16952)
-- Name: policy_evaluation_rule policy_evaluation_rule_policy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.policy_evaluation_rule
    ADD CONSTRAINT policy_evaluation_rule_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES public.procurement_policy(policy_id);


--
-- TOC entry 4739 (class 2606 OID 16970)
-- Name: policy_weight_config policy_weight_config_policy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.policy_weight_config
    ADD CONSTRAINT policy_weight_config_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES public.procurement_policy(policy_id);


--
-- TOC entry 4740 (class 2606 OID 16983)
-- Name: procurement_cycle procurement_cycle_enterprise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.procurement_cycle
    ADD CONSTRAINT procurement_cycle_enterprise_id_fkey FOREIGN KEY (enterprise_id) REFERENCES public.enterprise(enterprise_id);


--
-- TOC entry 4741 (class 2606 OID 16988)
-- Name: procurement_cycle procurement_cycle_policy_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.procurement_cycle
    ADD CONSTRAINT procurement_cycle_policy_id_fkey FOREIGN KEY (policy_id) REFERENCES public.procurement_policy(policy_id);


--
-- TOC entry 4735 (class 2606 OID 16915)
-- Name: procurement_policy procurement_policy_enterprise_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.procurement_policy
    ADD CONSTRAINT procurement_policy_enterprise_id_fkey FOREIGN KEY (enterprise_id) REFERENCES public.enterprise(enterprise_id);


--
-- TOC entry 4755 (class 2606 OID 17129)
-- Name: recommendation recommendation_cycle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.recommendation
    ADD CONSTRAINT recommendation_cycle_id_fkey FOREIGN KEY (cycle_id) REFERENCES public.procurement_cycle(cycle_id);


--
-- TOC entry 4731 (class 2606 OID 16880)
-- Name: regulation_document_requirement regulation_document_requirement_document_type_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.regulation_document_requirement
    ADD CONSTRAINT regulation_document_requirement_document_type_code_fkey FOREIGN KEY (document_type_code) REFERENCES public.document_type(document_type_code);


--
-- TOC entry 4732 (class 2606 OID 16875)
-- Name: regulation_document_requirement regulation_document_requirement_regulation_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.regulation_document_requirement
    ADD CONSTRAINT regulation_document_requirement_regulation_code_fkey FOREIGN KEY (regulation_code) REFERENCES public.regulation_framework(regulation_code);


--
-- TOC entry 4728 (class 2606 OID 16836)
-- Name: regulation_framework regulation_framework_data_sensitivity_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.regulation_framework
    ADD CONSTRAINT regulation_framework_data_sensitivity_code_fkey FOREIGN KEY (data_sensitivity_code) REFERENCES public.data_sensitivity(sensitivity_code);


--
-- TOC entry 4729 (class 2606 OID 16831)
-- Name: regulation_framework regulation_framework_software_category_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.regulation_framework
    ADD CONSTRAINT regulation_framework_software_category_code_fkey FOREIGN KEY (software_category_code) REFERENCES public.software_category(category_code);


--
-- TOC entry 4730 (class 2606 OID 16852)
-- Name: regulation_rule regulation_rule_regulation_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.regulation_rule
    ADD CONSTRAINT regulation_rule_regulation_code_fkey FOREIGN KEY (regulation_code) REFERENCES public.regulation_framework(regulation_code);


--
-- TOC entry 4745 (class 2606 OID 17029)
-- Name: vendor vendor_cycle_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.vendor
    ADD CONSTRAINT vendor_cycle_id_fkey FOREIGN KEY (cycle_id) REFERENCES public.procurement_cycle(cycle_id);


--
-- TOC entry 4746 (class 2606 OID 17050)
-- Name: vendor_document vendor_document_document_type_code_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.vendor_document
    ADD CONSTRAINT vendor_document_document_type_code_fkey FOREIGN KEY (document_type_code) REFERENCES public.document_type(document_type_code);


--
-- TOC entry 4747 (class 2606 OID 17045)
-- Name: vendor_document vendor_document_vendor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: doadmin
--

ALTER TABLE ONLY public.vendor_document
    ADD CONSTRAINT vendor_document_vendor_id_fkey FOREIGN KEY (vendor_id) REFERENCES public.vendor(vendor_id);


-- Completed on 2026-06-16 20:49:07

--
-- PostgreSQL database dump complete
--

\unrestrict P0RGL5UrSuc1QeZOUzFuhhJjtQA4RTnAos3pOdWJFJP1D9mH4mchVreetFtP8EL

