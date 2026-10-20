"""Local operator commands for schema migration and explicit legacy ownership recovery."""
import argparse,getpass
from .database import init_db,SessionLocal
from .models import User,Hospital
from .routers.auth import hash_password

def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('init')
    own=sub.add_parser('link-hospital');own.add_argument('--email',required=True);own.add_argument('--hospital-id',required=True)
    reset=sub.add_parser('set-password');reset.add_argument('--email',required=True)
    sub.add_parser('list-hospitals')
    args=parser.parse_args();init_db()
    if args.command=='init': print('Database initialized; additive migrations applied.');return
    with SessionLocal() as db:
        if args.command=='list-hospitals':
            for h in db.query(Hospital): print(h.id,h.name,'owner:',h.user_id or 'UNLINKED')
            return
        user=db.query(User).filter(User.email==args.email.strip().lower()).first()
        if not user: parser.error('Account not found')
        if args.command=='set-password':
            password=getpass.getpass('New password (at least 8 characters): ')
            if len(password)<8 or password!=getpass.getpass('Confirm password: '): parser.error('Password too short or confirmation mismatch')
            user.password_hash=hash_password(password)
        elif args.command=='link-hospital':
            if user.role not in ('HOSPITAL_ADMIN','HOSPITAL'): parser.error('Account is not a hospital administrator')
            hospital=db.get(Hospital,args.hospital_id)
            if not hospital: parser.error('Hospital not found')
            if hospital.user_id and hospital.user_id!=user.id: parser.error('Hospital already linked to another account')
            if db.query(Hospital).filter(Hospital.user_id==user.id,Hospital.id!=hospital.id).first(): parser.error('Account already owns another hospital')
            hospital.user_id=user.id
        db.commit();print('Saved.')

if __name__=='__main__': main()
