/* Inspect the first few bytes of an explicitly selected local file.
 * A matching magic header confirms only its format signature, NOT the content,
 * decoded RF protocol, satellite origin, or successful image/audio extraction.
 * No network access, full-file read, or file mutation.
 */
import {localFileKind} from "./reception_catalog.mjs";

const starts=(bytes,magic)=>magic.every((x,i)=>bytes[i]===x);
const ascii=(bytes,offset,value)=>[...value].every((c,i)=>bytes[offset+i]===c.charCodeAt(0));

export async function inspectLocalFormat(file) {
  if(!file || typeof file.name!=="string" || !Number.isFinite(file.size) || file.size<0 ||
     typeof file.slice!=="function") throw Error("Select a readable local file.");
  const ext=file.name.toLowerCase().split(".").pop();
  const kind=localFileKind(file.name);
  const head=new Uint8Array(await file.slice(0,24).arrayBuffer());
  let signature=null, label=null;
  switch(ext) {
    case "png":
      label="IMAGE · PNG";
      signature=starts(head,[137,80,78,71,13,10,26,10]);break;
    case "jpg":case "jpeg":
      label="IMAGE · JPEG";
      signature=starts(head,[255,216,255]);break;
    case "gif":
      label="IMAGE · GIF";
      signature=ascii(head,0,"GIF87a")||ascii(head,0,"GIF89a");break;
    case "webp":
      label="IMAGE · WEBP";
      signature=ascii(head,0,"RIFF")&&ascii(head,8,"WEBP");break;
    case "wav":
      label="AUDIO · WAV";
      signature=(ascii(head,0,"RIFF")||ascii(head,0,"RF64"))&&ascii(head,8,"WAVE");break;
    case "ogg":
      label="AUDIO · OGG";
      signature=ascii(head,0,"OggS");break;
    case "flac":
      label="AUDIO · FLAC";
      signature=ascii(head,0,"fLaC");break;
    case "mp3":
      label="AUDIO · MP3";
      signature=ascii(head,0,"ID3")||(head.length>=2 && head[0]===255 && (head[1]&0xe0)===0xe0);break;
    case "mp4":case "m4a":
      label=kind==="video"?"VIDEO · MP4":"AUDIO · M4A";
      signature=ascii(head,4,"ftyp");break;
    case "webm":
      label="VIDEO · WEBM";
      signature=starts(head,[26,69,223,163]);break;
    case "cu8":
      label="RAW RF · CU8";
      if(file.size%2!==0)
        return {kind,label,status:"size-warning",verifiedHeader:false,
          explanation:"Odd CU8 byte count: unsigned interleaved I/Q needs complete two-byte sample pairs. No satellite signal identified."};
      return {kind,label,status:"raw-unverified",verifiedHeader:false,
        explanation:"Unsigned interleaved I/Q assumed from the file extension. CU8 has no embedded frequency, sample rate, image or satellite identity."};
    case "iq":case "u8":case "cfile":
      return {kind,label:"RAW RF · UNVERIFIED",status:"raw-unverified",verifiedHeader:false,
        explanation:"Raw I/Q format and sample encoding must be supplied manually. The file does not certify a transmission or decoded data."};
    case "json":label="DATA · JSON";break;
    case "csv":label="TABLE · CSV";break;
    case "txt":case "tle":case "log":case "aprs":label="TEXT · "+ext.toUpperCase();break;
    case "mov":label="VIDEO · MOV";break;
    default:label="OTHER · "+ext.toUpperCase();break;
  }
  if(signature===false)
    return {kind,label,status:"header-mismatch",verifiedHeader:false,
      explanation:"Header does not match the filename extension. Do not call it a decoded image/audio/video file."};
  if(signature===true)
    return {kind,label,status:"header-match",verifiedHeader:true,
      explanation:"Recognizable format signature on disk. Complete decoding, genuine RF reception and satellite source remain unverified."};
  return {kind,label,status:"extension-only",verifiedHeader:false,
    explanation:"Format inferred only from the filename extension; no file signature or radio-protocol verification performed."};
}
