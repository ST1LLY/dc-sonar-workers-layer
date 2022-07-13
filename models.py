from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class NTLMDumpSession(Base):  # type: ignore
    __tablename__ = 'ntlm_dump_session'
    id = Column(Integer, primary_key=True)
    session_name = Column(String)
    domain_name = Column(String)
    domain_pk = Column(Integer, unique=True)

    def __repr__(self) -> str:
        return f"<NTLMDumpSessions(session_name='{self.session_name}', domain_name='{self.domain_name}', domain_pk='{self.domain_pk}')>"


class NTLMBruteSession(Base):  # type: ignore
    __tablename__ = 'ntlm_brute_session'
    id = Column(Integer, primary_key=True)
    session_name = Column(String)
    domain_name = Column(String)
    domain_pk = Column(Integer, unique=True)

    def __repr__(self) -> str:
        return f"<NTLMDumpSessions(session_name='{self.session_name}', domain_name='{self.domain_name}', domain_pk='{self.domain_pk}')>"


class NTLMDumpHash(Base):  # type: ignore
    __tablename__ = 'ntlm_dump_hash'
    id = Column(Integer, primary_key=True)
    domain_pk = Column(Integer)
    user_login = Column(String)
    user_ntlm_hash = Column(String)

    def __repr__(self) -> str:
        return f"<NTLMBruteHash(domain_pk='{self.domain_pk}', user_login='{self.user_login}', user_pass_hash='{self.user_ntlm_hash}')>"
