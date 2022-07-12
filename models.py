from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Date

Base = declarative_base()


class NTLMDumpSession(Base):
    __tablename__ = 'ntlm_dump_session'
    id = Column(Integer, primary_key=True)
    session_name = Column(String)
    domain_name = Column(String)
    domain_pk = Column(Integer, unique = True)

    def __repr__(self) -> str:
        return f"<NTLMDumpSessions(session_name='{self.session_name}', domain_name='{self.domain_name}', domain_pk='{self.domain_pk}')>"


class NTLMBruteSession(Base):
    __tablename__ = 'ntlm_brute_session'
    id = Column(Integer, primary_key=True)
    session_name = Column(String)
    domain_name = Column(String)
    domain_pk = Column(Integer, unique = True)

    def __repr__(self) -> str:
        return (
            f"<NTLMDumpSessions(session_name='{self.session_name}', domain_name='{self.domain_name}', domain_pk='{self.domain_pk}')>"
        )
