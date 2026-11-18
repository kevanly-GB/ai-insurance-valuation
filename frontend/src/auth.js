import {Amplify} from "aws-amplify";
import {signIn,signOut,signUp,confirmSignUp,resetPassword,confirmResetPassword,confirmSignIn,fetchAuthSession} from "aws-amplify/auth";
export const demo=import.meta.env.VITE_DEMO_MODE==="true";
if(!demo){Amplify.configure({Auth:{Cognito:{userPoolId:import.meta.env.VITE_COGNITO_USER_POOL_ID,userPoolClientId:import.meta.env.VITE_COGNITO_APP_CLIENT_ID,loginWith:{email:true}}}});}
export {signIn,signOut,signUp,confirmSignUp,resetPassword,confirmResetPassword,confirmSignIn};
export async function credentials(){
if(demo){const role=localStorage.getItem("dev-role");return role?{role,token:"dev-"+role}:null;}
try{const s=await fetchAuthSession(),t=s.tokens?.accessToken;return t?{token:t.toString(),role:(t.payload["cognito:groups"]||[]).includes("assessor")?"assessor":"claimant"}:null;}catch{return null;}
}